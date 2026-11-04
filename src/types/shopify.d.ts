export {};

declare global {
  interface Window {
    shopify?: {
      idToken: () => Promise<string>;
      config?: { shop?: string; apiKey?: string };
    };
  }
}
