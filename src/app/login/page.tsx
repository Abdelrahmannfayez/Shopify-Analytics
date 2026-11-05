"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Command, Eye, EyeOff, Globe2, LockKeyhole, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { signIn } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [arabic, setArabic] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const t = arabic
    ? { back:"العودة إلى لوحة التحكم", title:"مرحبًا بعودتك", desc:"سجّل الدخول إلى مساحة متجرك.", email:"البريد الإلكتروني", password:"كلمة المرور", submit:"تسجيل الدخول", signing:"جارٍ تسجيل الدخول…", error:"تعذر تسجيل الدخول. تحقق من بياناتك وحاول مرة أخرى.", secure:"تسجيل دخول آمن", language:"English", tagline:"كل ما يحدث في متجرك، في مكان واحد.", sub:"وضوح يومي لاتخاذ قرارات أفضل.", label:"ذكاء التجارة" }
    : { back:"Back to your dashboard", title:"Welcome back", desc:"Sign in to your store workspace.", email:"Email address", password:"Password", submit:"Sign in", signing:"Signing in…", error:"Could not sign in. Check your details and try again.", secure:"Secure sign in", language:"العربية", tagline:"Everything happening in your store, in one place.", sub:"Daily clarity for better decisions.", label:"Commerce intelligence" };

  useEffect(() => {
    const saved = window.localStorage.getItem("northstar_language");
    const nextArabic = saved === "ar";
    setArabic(nextArabic);
    document.documentElement.lang = nextArabic ? "ar" : "en";
    document.documentElement.dir = nextArabic ? "rtl" : "ltr";
  }, []);

  function toggleLanguage() {
    const nextArabic = !arabic;
    setArabic(nextArabic);
    window.localStorage.setItem("northstar_language", nextArabic ? "ar" : "en");
    document.documentElement.lang = nextArabic ? "ar" : "en";
    document.documentElement.dir = nextArabic ? "rtl" : "ltr";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn({ email, password });
      router.replace("/");
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : t.error);
    } finally {
      setLoading(false);
    }
  }

  return <main dir={arabic ? "rtl" : "ltr"} className="grid min-h-screen bg-white lg:grid-cols-[1fr_.88fr]">
    <section className="relative flex min-h-[300px] flex-col justify-between overflow-hidden bg-[#173b2c] p-7 text-white sm:p-11 lg:min-h-screen lg:p-14">
      <div className="absolute -right-24 top-20 h-80 w-80 rounded-full border border-white/10"/><div className="absolute -right-10 top-34 h-64 w-64 rounded-full border border-white/10"/><div className="absolute -bottom-40 -left-24 h-[460px] w-[460px] rounded-full border border-white/[.08]"/>
      <Link href="/" className="relative z-10 flex w-fit items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white/10"><Command size={20}/></span><span><b className="block text-[16px] tracking-tight">northstar</b><small className="text-[10px] text-white/55">{t.label}</small></span></Link>
      <div className="relative z-10 my-10 max-w-lg"><span className="mb-6 grid h-11 w-11 place-items-center rounded-2xl bg-[#ffffff14] text-[#b6dec5]"><Sparkles size={20}/></span><h1 className="max-w-md text-3xl font-semibold leading-tight tracking-[-.04em] sm:text-[42px]">{t.tagline}</h1><p className="mt-4 max-w-sm text-sm leading-6 text-white/65">{t.sub}</p><div className="mt-10 hidden items-center gap-2 text-xs text-white/60 sm:flex"><span className="h-2 w-2 animate-pulse rounded-full bg-[#7bd09a]"/>{arabic?"\u0631\u0624\u0649 \u0645\u0628\u0627\u0634\u0631\u0629 \u0644\u0646\u0645\u0648 \u0623\u0639\u0645\u0627\u0644\u0643":"Live insights for your business"}</div></div>
      <div className="relative z-10 hidden items-center justify-between text-[10px] text-white/45 lg:flex"><span>© 2026 Northstar Analytics</span><span className="flex items-center gap-1.5"><ShieldCheck size={13}/>{t.secure}</span></div>
    </section>
    <section className="flex items-center justify-center px-6 py-10 sm:px-12"><div className="w-full max-w-[380px]">
      <div className="mb-12 flex items-center justify-between"><Link href="/" className="flex items-center gap-1.5 text-xs font-medium text-[#78837d] transition hover:text-[#26764f]"><ArrowLeft size={14}/>{t.back}</Link><button onClick={toggleLanguage} className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-[#78837d] hover:bg-[#f3f6f3]"><Globe2 size={14}/>{t.language}</button></div>
      <h2 className="text-[28px] font-semibold tracking-[-.04em] text-[#18251e]">{t.title}</h2><p className="mt-2 text-sm text-[#87918b]">{t.desc}</p>
      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        <label className="block"><span className="mb-2 block text-xs font-semibold text-[#45534a]">{t.email}</span><span className="flex h-12 items-center gap-3 rounded-xl border border-[#e4eae5] px-3.5 transition focus-within:border-[#6ba683] focus-within:ring-4 focus-within:ring-[#eaf4ed]"><Mail size={16} className="text-[#96a19a]"/><input type="email" required autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} className="w-full bg-transparent text-sm text-[#24332a] outline-none placeholder:text-[#aeb7b1]" placeholder="you@yourstore.com"/></span></label>
        <label className="block"><span className="mb-2 block text-xs font-semibold text-[#45534a]">{t.password}</span><span className="flex h-12 items-center gap-3 rounded-xl border border-[#e4eae5] px-3.5 transition focus-within:border-[#6ba683] focus-within:ring-4 focus-within:ring-[#eaf4ed]"><LockKeyhole size={16} className="text-[#96a19a]"/><input type={showPassword?"text":"password"} required autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} className="w-full bg-transparent text-sm text-[#24332a] outline-none"/><button type="button" aria-label={showPassword?"Hide password":"Show password"} onClick={()=>setShowPassword(!showPassword)} className="text-[#96a19a] hover:text-[#47574d]">{showPassword?<EyeOff size={16}/>:<Eye size={16}/>}</button></span></label>
        {error&&<p role="alert" className="rounded-lg bg-[#fff0ed] px-3 py-2.5 text-xs leading-relaxed text-[#a7473d]">{error}</p>}
        <button type="submit" disabled={loading} className="flex h-12 w-full items-center justify-center rounded-xl bg-[#21734c] text-sm font-semibold text-white shadow-sm transition hover:bg-[#195f3e] focus:outline-none focus:ring-4 focus:ring-[#d7ecdd] disabled:cursor-wait disabled:opacity-70">{loading?t.signing:t.submit}</button>
      </form>
      <p className="mt-7 flex items-center justify-center gap-1.5 text-[11px] text-[#97a09a]"><ShieldCheck size={14}/>{t.secure}</p>
    </div></section>
  </main>;
}
