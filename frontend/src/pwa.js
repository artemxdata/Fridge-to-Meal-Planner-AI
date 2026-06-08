export function registerServiceWorker({ isProduction = import.meta.env.PROD, navigatorRef = navigator, windowRef = window } = {}) {
  if (!isProduction || !("serviceWorker" in navigatorRef)) {
    return;
  }

  windowRef.addEventListener("load", () => {
    navigatorRef.serviceWorker.register("/service-worker.js").catch((error) => {
      console.warn("Service worker registration failed", error);
    });
  });
}
