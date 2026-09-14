import React from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  ChevronRight,
  Shield,
  Cpu,
  Lock,
  CheckCircle,
} from 'lucide-react';
import MonitoringDashboard from './MonitoringDashboard';

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: 'easeOut' },
  },
};

export default function Hero({ onOpenDemo }) {
  return (
    <section id="inicio" className="w-full">
      {/* ========================================================================= */}
      {/* 1. PORTADA TECNOLÓGICA DE PANTALLA COMPLETA (EDGE-TO-EDGE COVER)           */}
      {/* ========================================================================= */}
      <div className="relative w-full overflow-hidden border-b border-slate-800 bg-slate-950 pt-32 pb-20 sm:pt-36 sm:pb-28">
        
        {/* ======================================================================= */}
        {/* MALLA VECTORIAL ANIMADA, LÁSER Y RESPLANDOR NEÓN DE BORDE A BORDE       */}
        {/* ======================================================================= */}
        <div className="pointer-events-none absolute inset-0 select-none overflow-hidden">
          {/* Resplandores ambientales */}
          <div className="absolute left-1/2 -top-24 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-[130px]" />
          <div className="absolute top-1/2 -left-20 h-80 w-80 rounded-full bg-teal-500/15 blur-[100px]" />
          <div className="absolute top-1/2 -right-20 h-80 w-80 rounded-full bg-cyan-500/15 blur-[100px]" />

          {/* Malla Vectorial de Circuitos IA (SVG Neural Grid) de ancho completo */}
          <svg
            className="absolute inset-0 h-full w-full opacity-65"
            preserveAspectRatio="none"
            viewBox="0 0 1400 600"
          >
            <defs>
              <linearGradient id="fullCoverGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.9" />
                <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.7" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.2" />
              </linearGradient>
              <linearGradient id="fullCoverGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#10b981" stopOpacity="0.2" />
              </linearGradient>
              <filter id="fullCoverGlow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Circuitos y vectores tecnológicos de borde a borde */}
            <path
              d="M 0 100 Q 350 240 700 70 T 1400 160"
              fill="none"
              stroke="url(#fullCoverGrad1)"
              strokeWidth="2.5"
              strokeDasharray="10 6"
              filter="url(#fullCoverGlow)"
            />
            <path
              d="M 0 280 C 400 80, 1000 400, 1400 130"
              fill="none"
              stroke="url(#fullCoverGrad2)"
              strokeWidth="2"
              strokeDasharray="8 6"
              filter="url(#fullCoverGlow)"
            />
            <path
              d="M 0 450 Q 450 280 900 500 T 1400 340"
              fill="none"
              stroke="#10b981"
              strokeWidth="1.5"
              opacity="0.35"
            />

            {/* Grid ortogonal */}
            <line x1="200" y1="0" x2="350" y2="600" stroke="#10b981" strokeWidth="0.8" strokeDasharray="5 5" opacity="0.3" />
            <line x1="550" y1="0" x2="700" y2="600" stroke="#06b6d4" strokeWidth="0.8" strokeDasharray="5 5" opacity="0.3" />
            <line x1="900" y1="0" x2="1050" y2="600" stroke="#10b981" strokeWidth="0.8" strokeDasharray="5 5" opacity="0.3" />
            <line x1="1250" y1="0" x2="1350" y2="600" stroke="#06b6d4" strokeWidth="0.8" strokeDasharray="5 5" opacity="0.3" />

            {/* Nodos de IA luminosos */}
            <g filter="url(#fullCoverGlow)">
              <circle cx="200" cy="145" r="6" fill="#10b981" />
              <circle cx="350" cy="235" r="5" fill="#34d399" />
              <circle cx="700" cy="70" r="7" fill="#06b6d4" />
              <circle cx="1000" cy="255" r="5.5" fill="#10b981" />
              <circle cx="1250" cy="145" r="6" fill="#34d399" />
              <circle cx="550" cy="180" r="5" fill="#06b6d4" />
            </g>
          </svg>

          {/* Estela de luz cinematográfica amplia, suave y con velocidad lenta */}
          <motion.div
            animate={{ left: ['-40%', '140%'] }}
            transition={{ duration: 8.5, repeat: Infinity, ease: 'linear' }}
            className="pointer-events-none absolute inset-y-0 w-[550px] -skew-x-12"
          >
            <div className="h-full w-full bg-gradient-to-r from-transparent via-emerald-400/25 via-teal-300/30 to-transparent blur-2xl" />
          </motion.div>

          {/* Scanlines de CCTV */}
          <div className="cctv-scanlines pointer-events-none absolute inset-0 opacity-25" />
        </div>

        {/* ======================================================================= */}
        {/* CONTENIDO EXCLUSIVO ENMARCADO EN LA PORTADA                             */}
        {/* ======================================================================= */}
        <div className="relative z-10 mx-auto max-w-5xl px-4 text-center sm:px-6 lg:px-8">
          
          {/* Badge superior */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mx-auto mb-6 inline-flex items-center gap-2.5 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-4 py-1.5 text-xs font-bold tracking-wider text-emerald-300 backdrop-blur-md shadow-lg shadow-emerald-500/10"
          >
            <Cpu size={15} className="text-emerald-400 animate-pulse" />
            <span>VISION AI · PLATAFORMA DE SEGURIDAD INDUSTRIAL</span>
            <span className="rounded-full bg-emerald-400/25 px-2 py-0.5 text-[10px] font-extrabold text-emerald-200 uppercase">
              EN VIVO
            </span>
          </motion.div>

          {/* Gran Titular */}
          <motion.h1
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mx-auto max-w-4xl text-balance text-4xl font-extrabold tracking-tight text-white sm:text-5xl md:text-6xl lg:text-7xl"
          >
            La seguridad de tus operarios.{' '}
            <span className="block bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
              Supervisada en tiempo real.
            </span>
          </motion.h1>

          {/* Subtítulo explicativo */}
          <motion.p
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg"
          >
            Vision analiza los feeds de tus cámaras de seguridad existentes mediante visión artificial para auditar, en milisegundos, el uso reglamentario de Elementos de Protección Personal (EPP).
          </motion.p>

          {/* Botones de acción */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mt-9 flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <button
              onClick={onOpenDemo}
              className="group inline-flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-8 py-4 text-sm font-bold text-white shadow-xl shadow-emerald-500/30 transition-all duration-200 hover:from-emerald-600 hover:to-teal-600 hover:shadow-emerald-500/45 active:scale-95 sm:w-auto"
            >
              <span>Solicitar una demostración</span>
              <ArrowRight size={17} className="transition-transform group-hover:translate-x-1" />
            </button>

            <a
              href="#como-funciona"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 px-7 py-4 text-sm font-semibold text-slate-200 backdrop-blur-sm transition-all hover:bg-slate-800 hover:border-slate-600 sm:w-auto"
            >
              <span>Conocer cómo funciona</span>
              <ChevronRight size={17} />
            </a>
          </motion.div>

          {/* Insignias de confianza en la base de la portada */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            className="mt-12 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-xs font-medium text-slate-400"
          >
            <div className="flex items-center gap-2">
              <CheckCircle size={15} className="text-emerald-400" />
              <span>Compatible con cámaras RTSP/ONVIF</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield size={15} className="text-emerald-400" />
              <span>Reportes de auditoría y trazabilidad digital</span>
            </div>
            <div className="flex items-center gap-2">
              <Lock size={15} className="text-emerald-400" />
              <span>Edge Computing On-Premise</span>
            </div>
          </motion.div>
        </div>

      </div>

      {/* ========================================================================= */}
      {/* 2. CONSOLA DE MONITOREO CCTV (UBICADA FUERA DE LA PORTADA)               */}
      {/* ========================================================================= */}
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="mx-auto max-w-3xl text-center mb-10">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 dark:bg-emerald-400" />
            <span>CONSOLA OPERACIONAL EN TIEMPO REAL</span>
          </div>
          <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl dark:text-white">
            Simulador de Detección y Análisis en Vivo
          </h2>
          <p className="mt-2 text-sm font-medium text-slate-600 dark:text-slate-300">
            Interactúa con la consola para comprobar cómo el motor de IA identifica el EPP en diferentes cámaras de planta.
          </p>
        </div>

        <MonitoringDashboard />
      </div>
    </section>
  );
}
