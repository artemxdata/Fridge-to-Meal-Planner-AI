import { describe, expect, it, vi } from "vitest";

import { registerServiceWorker } from "./pwa.js";

describe("PWA registration", () => {
  it("registers the service worker only for production builds", () => {
    const register = vi.fn(() => Promise.resolve());
    const addEventListener = vi.fn((event, callback) => callback());

    registerServiceWorker({
      isProduction: true,
      navigatorRef: { serviceWorker: { register } },
      windowRef: { addEventListener },
    });

    expect(addEventListener).toHaveBeenCalledWith("load", expect.any(Function));
    expect(register).toHaveBeenCalledWith("/service-worker.js");
  });

  it("skips registration outside production", () => {
    const register = vi.fn();
    const addEventListener = vi.fn();

    registerServiceWorker({
      isProduction: false,
      navigatorRef: { serviceWorker: { register } },
      windowRef: { addEventListener },
    });

    expect(addEventListener).not.toHaveBeenCalled();
    expect(register).not.toHaveBeenCalled();
  });
});
