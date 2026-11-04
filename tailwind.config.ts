import type { Config } from "tailwindcss";
const config: Config = { content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"], theme: { extend: { colors: { ink: "#17241f", muted: "#74817b", canvas: "#f5f7f4", green: "#18865b" }, boxShadow: { card: "0 2px 12px rgba(23,36,31,.045)" } } }, plugins: [] };
export default config;
