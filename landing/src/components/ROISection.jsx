import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, TrendingDown, Database, Cpu, CheckCircle2, SlidersHorizontal, Lock, Zap } from 'lucide-react';

export default function ROISection({ onOpenDemo }) {
  const benefits = [
    {
      title: "Cero inversión en nuevo hardware",
      description: "Vision se conecta a tus cámaras IP y sistemas DVR/NVR existentes mediante protocolos estándar (RTSP / ONVIF).",
      icon: Database,
    },
    {
      title: "Auditorías continuas y respaldo digital",
      description: "Generación automática de evidencia con estampas de tiempo cifradas para inspecciones internas y comités de seguridad.",
      icon: ShieldCheck,
    },
    {
      title: "Reducción drástica de siniestralidad",
      description: "La corrección temprana de hábitos inseguros reduce incidentes graves y primas de seguros laborales.",
      icon: TrendingDown,
    },
    {
      title: "Privacidad y Cumplimiento Normativo",
      description: "Anonimización facial y procesamiento en borde (Edge) para garantizar el cumplimiento de normativas de datos laborales.",
      icon: Lock,
    },
  ];

  return (
    <section id="normativas" className="py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-slate-200/80 bg-gradient-to-b from-slate-50 to-white p-8 sm:p-12 lg:p-16 dark:border-slate-800/80 dark:from-slate-900/80 dark:to-slate-950">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            {/* Left Column: Heading and value proposition */}
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                <Zap size={14} />
                <span>INTEGRACIÓN RÁPIDA & ROI INDUSTRIAL</span>
              </div>

              <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl dark:text-white">
                Transformá tu infraestructura existente en un centro de prevención
              </h2>

              <p className="mt-4 text-base font-normal sm:font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                No necesitás reemplazar cámaras ni desplegar costosos sensores portátiles. Vision se acopla a tu red de seguridad en cuestión de horas y comienza a detectar desviaciones desde el primer día.
              </p>

              <div className="mt-8 space-y-3.5">
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                    <CheckCircle2 size={16} />
                  </div>
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    Plug & Play con NVRs Hikvision, Dahua, Axis
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                    <CheckCircle2 size={16} />
                  </div>
                  <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    Alertas automáticas a Supervisores
                  </span>
                </div>
              </div>
            </div>

            {/* Right Column: 2x2 Grid of enterprise benefits */}
            <div className="grid gap-4 sm:grid-cols-2">
              {benefits.map((b) => {
                const Icon = b.icon;
                return (
                  <div
                    key={b.title}
                    className="rounded-2xl border border-slate-200/80 bg-white/70 p-6 sm:p-7 backdrop-blur-sm transition-all hover:border-emerald-500/40 hover:shadow-md dark:border-slate-800 dark:bg-slate-900/60"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                      <Icon size={20} />
                    </div>
                    <h3 className="mt-4 text-sm font-bold text-slate-900 dark:text-white">
                      {b.title}
                    </h3>
                    <p className="mt-2 text-xs font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                      {b.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
