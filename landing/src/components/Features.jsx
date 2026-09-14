import React from 'react';
import { motion } from 'framer-motion';
import {
  Video,
  HardHat,
  AlertOctagon,
  BarChart3,
  Layers,
  Cpu,
  Clock,
  ShieldAlert,
  ArrowUpRight,
} from 'lucide-react';

const features = [
  {
    icon: Video,
    tag: "Procesamiento Continuo",
    title: "Detección en tiempo real",
    description:
      "Analiza de forma continua múltiples feeds de video IP (RTSP/ONVIF) identificando incumplimientos en menos de 20ms por cuadro.",
    highlight: "30 FPS por canal",
  },
  {
    icon: HardHat,
    tag: "Visión Computacional",
    title: "Reconocimiento granular de EPP",
    description:
      "Modelos entrenados para identificar cascos, chalecos de alta visibilidad, protección ocular, arneses de altura y calzado de seguridad.",
    highlight: "+99% precisión",
  },
  {
    icon: AlertOctagon,
    tag: "Respuesta Inmediata",
    title: "Alertas inteligentes y multicanal",
    description:
      "Genera avisos instantáneos ante condiciones de riesgo crítico mediante WhatsApp, Telegram, balizas lumínicas o integración con SCADA.",
    highlight: "Notificación < 1s",
  },
  {
    icon: BarChart3,
    tag: "Auditoría y Métricas",
    title: "Monitoreo y analítica centralizada",
    description:
      "Tableros de control con índices de cumplimiento, mapas de calor de riesgo por planta y reportes automáticos para comités de seguridad.",
    highlight: "Reportes automatizados",
  },
];

export default function Features() {
  return (
    <section
      id="como-funciona"
      className="relative border-y border-slate-200/80 bg-slate-50/70 py-24 dark:border-slate-800/80 dark:bg-slate-900/40"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400" />
            <span>TECNOLOGÍA DE DETECCIÓN ACTIVA</span>
          </div>

          <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl dark:text-white">
            De la cámara de seguridad a una decisión preventiva
          </h2>

          <p className="mt-4 text-base font-normal sm:font-medium leading-relaxed text-slate-600 sm:text-lg dark:text-slate-300">
            Vision transforma el video pasivo de tus instalaciones en una capa activa de prevención de accidentes y auditoría continua.
          </p>
        </div>

        {/* Feature Cards Grid */}
        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="group relative flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-7 sm:p-8 shadow-sm transition-all duration-300 hover:-translate-y-1.5 hover:border-emerald-500/40 hover:shadow-xl hover:shadow-emerald-500/5 dark:border-slate-800 dark:bg-slate-900/90 dark:hover:border-emerald-500/40"
              >
                <div>
                  {/* Top Bar: Icon + Highlight Tag */}
                  <div className="flex items-center justify-between">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-700 transition-colors duration-300 group-hover:bg-emerald-600 group-hover:text-white dark:bg-emerald-500/15 dark:text-emerald-400">
                      <Icon size={24} />
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {feature.highlight}
                    </span>
                  </div>

                  {/* Feature Content */}
                  <div className="mt-6">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                      {feature.tag}
                    </span>
                    <h3 className="mt-1 text-lg font-bold text-slate-900 transition-colors group-hover:text-emerald-700 dark:text-white dark:group-hover:text-emerald-400">
                      {feature.title}
                    </h3>
                    <p className="mt-3 text-sm leading-relaxed text-slate-600 font-medium dark:text-slate-300">
                      {feature.description}
                    </p>
                  </div>
                </div>

                {/* Footer link cue */}
                <div className="mt-6 flex items-center gap-1 text-xs font-bold text-emerald-700 opacity-0 transition-opacity duration-300 group-hover:opacity-100 dark:text-emerald-400">
                  <span>Ver especificación técnica</span>
                  <ArrowUpRight size={14} />
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
