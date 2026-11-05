import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = { title: "Northstar — Shopify analytics", description: "Your store, in focus." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const shopifyClientId = process.env.NEXT_PUBLIC_SHOPIFY_CLIENT_ID;
  return <html lang="en" suppressHydrationWarning><head>{shopifyClientId&&<><meta name="shopify-api-key" content={shopifyClientId}/><meta name="shopify-disabled-features" content="fetch"/><Script src="https://cdn.shopify.com/shopifycloud/app-bridge.js" strategy="beforeInteractive"/></>}</head><body>{children}</body></html>;
}
