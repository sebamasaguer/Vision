import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, Eye, Zap, Target, Award, HeartHandshake } from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: 'easeOut' },
  },
};

export default function Mission() {
  const metrics = [
    {
      icon: Eye,
      value: "24/7",
      label: "Monitoreo continuo autónomo",
      detail: "Sin fatiga visual humana ni puntos ciegos",
    },
    {
      icon: Zap,
      value: "< 20ms",
      label: "Velocidad de inferencia",
      detail: "Detección instantánea en el borde",
    },
    {
      icon: Target,
      value: "0 Meta",
      label: "Accidentes laborales",
      detail: "Prevención proactiva antes del siniestro",
    },
    {
      icon: ShieldCheck,
      value: "100%",
      label: "Trazabilidad de auditoría",
      detail: "Evidencia visual y registros en la nube",
    },
  ];

  return (
    <section id="mision" className="relative overflow-hidden py-24">
      {/* Background radial accent */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute right-0 top-1/2 h-[450px] w-[550px] -translate-y-1/2 rounded-full bg-emerald-500/10 blur-[130px]" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid items-center gap-14 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Left Column: Mission Manifesto */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
          >
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              <ShieldCheck size={16} />
              <span>NUESTRO MANIFIESTO</span>
            </div>

            <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl dark:text-white">
              La seguridad no debería depender de que alguien mire una pantalla.
            </h2>

            <p className="mt-6 text-base font-normal sm:font-medium leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
              En operaciones industriales dinámicas, los supervisores no pueden mantener la vista fija en decenas de monitores simultáneamente. Vision nace para convertir la infraestructura de video existente en una capa inteligente de prevención activa.
            </p>

            <p className="mt-4 text-base font-normal sm:font-medium leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
              Nuestro compromiso es ayudar a las organizaciones industriales a proteger a cada operario, garantizando que el uso de EPP no sea una regla en papel, sino una realidad supervisada en cada segundo de la jornada.
            </p>

            <div className="mt-8 flex items-center gap-4 border-t border-slate-200 pt-6 dark:border-slate-800">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                <HeartHandshake size={24} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                  Cultura preventiva primero
                </h4>
                <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
                  Empoderamos a los equipos de HyS con datos certeros para crear ambientes de trabajo protegidos.
                </p>
              </div>
            </div>
          </motion.div>

          {/* Right Column: Key Metrics Grid */}
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={fadeUp}
            className="grid grid-cols-2 gap-4"
          >
            {metrics.map((metric, idx) => {
              const Icon = metric.icon;
              return (
                <div
                  key={metric.label}
                  className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm transition-all hover:border-emerald-500/40 hover:shadow-md dark:border-slate-800 dark:bg-slate-900/90"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400">
                    <Icon size={20} />
                  </div>

                  <p className="mt-6 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl dark:text-white">
                    {metric.value}
                  </p>

                  <h3 className="mt-1 text-sm font-bold text-slate-800 dark:text-slate-200">
                    {metric.label}
                  </h3>

                  <p className="mt-1 text-xs font-medium text-slate-600 dark:text-slate-300">
                    {metric.detail}
                  </p>
                </div>
              );
            })}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
