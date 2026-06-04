import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from ultralytics import YOLO
from typing import List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import hashlib
from datetime import datetime, timedelta
from io import BytesIO


class AdvancedFoodVision:
    def __init__(self):
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.detection_cache: Dict[str, Dict[str, Any]] = {}
        self.model_loaded = False

        # ======= Маппинг классов =======
        # Оставляем только осмысленные «ингредиенты».
        # Шумные классы из COCO уводим в None, чтобы игнорировать.
        self.food_mapping = {
            # Фрукты
            'apple': 'яблоко', 'banana': 'банан', 'orange': 'апельсин', 'lemon': 'лимон',
            'grape': 'виноград', 'strawberry': 'клубника', 'pear': 'груша', 'peach': 'персик',
            'kiwi': 'киви', 'pineapple': 'ананас', 'watermelon': 'арбуз', 'melon': 'дыня',

            # Овощи
            'carrot': 'морковь', 'potato': 'картофель', 'tomato': 'помидор', 'cucumber': 'огурец',
            'onion': 'лук', 'garlic': 'чеснок', 'broccoli': 'брокколи', 'cabbage': 'капуста',
            'lettuce': 'салат', 'spinach': 'шпинат', 'eggplant': 'баклажан', 'zucchini': 'кабачок',
            'corn': 'кукуруза', 'mushroom': 'грибы', 'avocado': 'авокадо', 'bell pepper': 'болгарский перец',

            # Белки / молочка
            'chicken': 'курица', 'beef': 'говядина', 'pork': 'свинина', 'fish': 'рыба',
            'salmon': 'лосось', 'tuna': 'тунец', 'shrimp': 'креветки', 'egg': 'яйца',
            'cheese': 'сыр', 'yogurt': 'йогурт', 'milk': 'молоко', 'tofu': 'тофу',

            # Углеводы
            'bread': 'хлеб', 'rice': 'рис', 'pasta': 'паста', 'noodles': 'лапша',
            'flour': 'мука', 'oats': 'овсянка', 'quinoa': 'киноа',

            # Шумные/общие — игнорируем
            'person': None, 'bicycle': None, 'car': None,
            'bottle': None,         # раньше: «бутылка с жидкостью» — даёт шум
            'wine glass': None,     # напитки без распознавания этикетки — шум
            'cup': None,
            'bowl': None,           # «еда в миске» — шум
            'fork': None, 'knife': None, 'spoon': None,
            'pizza': 'пицца', 'donut': 'выпечка', 'cake': 'торт', 'sandwich': 'бутерброд', 'hot dog': 'сосиски',
        }

        # ======= Цветовой анализ (ужесточённые пороги) =======
        self.color_food_mapping = {
            'tomato': {'h_range': (0, 10), 'h_range2': (160, 180), 's_min': 130, 'v_min': 80},
            'carrot': {'h_range': (10, 25), 's_min': 110, 'v_min': 110},
            'banana': {'h_range': (20, 30), 's_min': 90, 'v_min': 160},
            'cucumber': {'h_range': (40, 80), 's_min': 55, 'v_min': 55},
            'apple_red': {'h_range': (0, 10), 'h_range2': (160, 180), 's_min': 90, 'v_min': 90},
            'apple_green': {'h_range': (40, 80), 's_min': 70, 'v_min': 70},
            'lettuce': {'h_range': (40, 80), 's_min': 50, 'v_min': 50},
            'orange': {'h_range': (10, 25), 's_min': 130, 'v_min': 130},
        }

    async def load_model(self):
        if self.model_loaded:
            return
        loop = asyncio.get_event_loop()
        self.model = await loop.run_in_executor(self.executor, self._load_yolo_model)
        self.model_loaded = True
        print("🤖 YOLOv8 модель загружена успешно!")

    def _load_yolo_model(self):
        try:
            model_path = "ml_models/ingredient_detection/food_yolo.pt"
            if os.path.exists(model_path):
                print(f"📁 Загружаем кастомную модель: {model_path}")
                return YOLO(model_path)
            else:
                print("📥 Загружаем предобученную YOLOv8n модель...")
                model = YOLO('yolov8n.pt')  # nano версия для скорости
                os.makedirs("ml_models/ingredient_detection", exist_ok=True)
                # model.save("ml_models/ingredient_detection/yolov8n.pt")  # не обязательно
                return model
        except Exception as e:
            print(f"⚠️ Ошибка загрузки YOLO: {e}")
            print("🔄 Используем fallback распознавание...")
            return None

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image = ImageEnhance.Contrast(image).enhance(1.15)
        image = ImageEnhance.Sharpness(image).enhance(1.1)
        image = ImageEnhance.Color(image).enhance(1.05)
        image = image.filter(ImageFilter.GaussianBlur(radius=0.4))
        target = (640, 640)
        image.thumbnail(target, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", target, (255, 255, 255))
        x = (target[0] - image.size[0]) // 2
        y = (target[1] - image.size[1]) // 2
        canvas.paste(image, (x, y))
        return canvas

    def analyze_image_colors(self, image: Image.Image) -> List[Dict[str, Any]]:
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        hsv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2HSV)
        h, w = hsv_image.shape[:2]
        image_area = h * w

        detected = []
        for food_name, cfg in self.color_food_mapping.items():
            h_min, h_max = cfg['h_range']
            s_min, v_min = cfg['s_min'], cfg['v_min']

            lower = np.array([h_min, s_min, v_min])
            upper = np.array([h_max, 255, 255])
            mask1 = cv2.inRange(hsv_image, lower, upper)

            mask = mask1
            if 'h_range2' in cfg:
                h_min2, h_max2 = cfg['h_range2']
                lower2 = np.array([h_min2, s_min, v_min])
                upper2 = np.array([h_max2, 255, 255])
                mask2 = cv2.inRange(hsv_image, lower2, upper2)
                mask = cv2.bitwise_or(mask1, mask2)

            total_pixels = mask.size
            colored_pixels = cv2.countNonZero(mask)
            percentage = (colored_pixels / total_pixels) * 100

            # пороги ужесточили
            if percentage < 8:
                continue

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < 2000:  # больше минимальная площадь
                    continue
                x, y, bw, bh = cv2.boundingRect(c)
                area_frac = area / image_area
                conf = min(0.9, (percentage / 18) * (area_frac / 0.02 + 0.6))

                if conf > 0.35:
                    ru = 'красное яблоко' if food_name == 'apple_red' else \
                         'зеленое яблоко' if food_name == 'apple_green' else food_name.replace('_', ' ')
                    detected.append({
                        'name': ru,
                        'confidence': round(float(conf), 3),
                        'detection_method': 'color_analysis',
                        'area_percentage': round(percentage, 1),
                        'bounding_box': [int(x), int(y), int(bw), int(bh)]
                    })
        return detected

    def estimate_expiry_date(self, food_name: str, visual_condition: str = "fresh") -> int:
        expiry_estimates = {
            'салат': 2, 'зелень': 2, 'шпинат': 2, 'листья': 2,
            'клубника': 2, 'малина': 2, 'черника': 3,
            'рыба': 2, 'креветки': 2, 'морепродукты': 2,
            'молоко': 3, 'кефир': 3, 'сметана': 4,

            'помидор': 5, 'огурец': 5, 'болгарский перец': 6,
            'брокколи': 5, 'цветная капуста': 6, 'баклажан': 6,
            'курица': 5, 'мясо': 4, 'фарш': 2,
            'йогурт': 7, 'творог': 5, 'сыр мягкий': 7,

            'морковь': 14, 'капуста': 14, 'свекла': 21,
            'лук': 30, 'чеснок': 30, 'картофель': 30,
            'яблоко': 10, 'апельсин': 12, 'лимон': 14,
            'яйца': 21, 'сыр твердый': 30,

            'рис': 365, 'гречка': 365, 'макароны': 365,
            'мука': 180, 'сахар': 365, 'соль': 365,
            'масло растительное': 180, 'уксус': 365,
        }

        multipliers = {'excellent': 1.2, 'fresh': 1.0, 'good': 0.8, 'fair': 0.5, 'poor': 0.2, 'wilted': 0.1}
        food_lower = food_name.lower()
        days = 7
        for prod, d in expiry_estimates.items():
            if prod in food_lower or food_lower in prod:
                days = d
                break
        mult = multipliers.get(visual_condition, 1.0)
        return max(1, int(days * mult))

    def analyze_image_quality(self, image: Image.Image) -> Dict[str, Any]:
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        brightness = float(np.mean(gray))
        contrast = float(gray.std())
        return {
            'sharpness': round(lap, 2),
            'brightness': round(brightness, 2),
            'contrast': round(contrast, 2),
            'blur_score': round(lap, 2),
            'overall_quality': 'good' if lap > 100 and 50 < brightness < 200 else 'poor'
        }

    def get_cache_key(self, image: Image.Image) -> str:
        buf = BytesIO()
        image.save(buf, format='JPEG')
        return hashlib.md5(buf.getvalue()).hexdigest()

    async def detect_food_items(self, image: Image.Image) -> Dict[str, Any]:
        cache_key = self.get_cache_key(image)
        if cache_key in self.detection_cache:
            cached = self.detection_cache[cache_key]
            if datetime.now() - datetime.fromisoformat(cached['timestamp']) < timedelta(hours=1):
                cached['from_cache'] = True
                return cached

        processed = self.preprocess_image(image)
        quality = self.analyze_image_quality(processed)
        await self.load_model()

        detected: List[Dict[str, Any]] = []
        methods = []

        # 1) YOLO (строже пороги + фильтры)
        if self.model:
            y = await self._detect_with_yolo(processed)
            detected.extend(y)
            methods.append("yolo")

        # 2) Цветовой анализ (строже пороги)
        c = self.analyze_image_colors(processed)
        detected.extend(c)
        methods.append("color_analysis")

        # Уникализация
        unique = self._remove_duplicates(detected)
        unique.sort(key=lambda x: x['confidence'], reverse=True)

        # Срок годности
        for it in unique:
            it['expires_in_days'] = self.estimate_expiry_date(
                it['name'],
                'fresh' if it['confidence'] > 0.7 else 'good'
            )

        result = {
            'detected_items': unique[:10],
            'total_detected': len(unique),
            'image_quality': quality,
            'detection_methods': methods,
            'processing_time': 0.5,
            'timestamp': datetime.now().isoformat(),
            'from_cache': False
        }
        self.detection_cache[cache_key] = result
        return result

    async def _detect_with_yolo(self, image: Image.Image) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._yolo_inference, image)

    def _yolo_inference(self, image: Image.Image) -> List[Dict[str, Any]]:
        try:
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            # Порог уверенности жёстче, фильтр по площади бокса
            results = self.model(cv_image, conf=0.45)  # было 0.3
            h, w = cv_image.shape[:2]
            min_box_area = 0.005 * (h * w)  # 0.5% площади кадра

            items: List[Dict[str, Any]] = []
            for res in results:
                boxes = res.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    class_name = self.model.names[cls]

                    ru = self.food_mapping.get(class_name, None)
                    if ru is None:
                        continue  # игнорируем шумные классы

                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    bw, bh = float(x2 - x1), float(y2 - y1)
                    if bw * bh < min_box_area:
                        continue  # слишком маленький бокс — шум

                    items.append({
                        'name': ru,
                        'confidence': round(conf, 3),
                        'detection_method': 'yolo',
                        'class_name': class_name,
                        'bounding_box': [int(x1), int(y1), int(bw), int(bh)]
                    })
            return items
        except Exception as e:
            print(f"Ошибка YOLO инференса: {e}")
            return []

    def _remove_duplicates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            key = it['name'].lower().strip()
            groups.setdefault(key, []).append(it)

        unique: List[Dict[str, Any]] = []
        for _, group in groups.items():
            group.sort(key=lambda x: x['confidence'], reverse=True)
            best = dict(group[0])
            methods = {g['detection_method'] for g in group}
            best['detection_methods'] = sorted(list(methods))
            if len(group) > 1:
                avg_conf = sum(g['confidence'] for g in group) / len(group)
                best['confidence'] = round(min(0.95, max(best['confidence'], avg_conf * 1.05)), 3)
            unique.append(best)
        return unique


# Глобальный экземпляр
food_vision = AdvancedFoodVision()


async def detect_ingredients_from_image(image: Image.Image) -> Dict[str, Any]:
    return await food_vision.detect_food_items(image)