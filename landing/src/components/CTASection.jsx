import React from 'react';
import { ArrowRight, ShieldCheck, Sparkles, CheckCircle2 } from 'lucide-react';

export default function CTASection({ onOpenDemo }) {
  return (
    <section id="contacto" className="relative px-4 pb-20 sm:px-6 lg:px-8">
      <div className="relative mx-auto max-w-7xl overflow-hidden rounded-3xl border border-emerald-500/30 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 px-6 py-16 text-center text-white shadow-2xl sm:px-12 sm:py-20 lg:py-24">
        {/* Glow backdrop */}
        <div className="pointer-events-none absolute left-1/2 top-0 h-[300px] w-[600px] -translate-x-1/2 rounded-full bg-emerald-500/25 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-10 right-10 h-[200px] w-[300px] rounded-full bg-teal-500/15 blur-[90px]" />

        <div className="relative z-10 mx-auto max-w-3xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-emerald-400 backdrop-blur-md">
            <Sparkles size={14} />
            <span>DESPLIEGUE EN MENOS DE 48 HORAS</span>
          </div>

          <h2 className="mt-6 text-3xl font-extrabold tracking-tight sm:text-4xl lg:text-5xl">
            Convertí tus cámaras en una capa inteligente de seguridad
          </h2>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
            Descubrí cómo Vision puede integrarse a tu operación actual, auditar el uso de EPP y transformar la prevención de accidentes en información accionable en tiempo real.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <button
              onClick={onOpenDemo}
              className="group inline-flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-8 py-4 text-sm font-bold text-white shadow-xl shadow-emerald-500/25 transition-all duration-200 hover:from-emerald-600 hover:to-teal-600 hover:shadow-emerald-500/40 active:scale-95 sm:w-auto"
            >
              <span>Solicitar demostración sin costo</span>
              <ArrowRight size={17} className="transition-transform group-hover:translate-x-1" />
            </button>

            <a
              href="mailto:contacto@vision.ai"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 px-7 py-4 text-sm font-semibold text-slate-200 transition-all hover:bg-slate-800 hover:border-slate-600 sm:w-auto"
            >
              <span>Contactar a Ventas Corporativas</span>
            </a>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-400">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={15} className="text-emerald-400" />
              <span>Sin contratos de permanencia</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={15} className="text-emerald-400" />
              <span>Compatible con cámaras actuales</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={15} className="text-emerald-400" />
              <span>Soporte técnico 24/7</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
