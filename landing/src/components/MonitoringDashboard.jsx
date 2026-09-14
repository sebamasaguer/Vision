import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck,
  Video,
  AlertTriangle,
  CheckCircle2,
  Activity,
  Maximize2,
  RefreshCw,
  HardHat,
  Eye,
  Sliders,
  Layers,
  Sparkles,
  Volume2,
  VolumeX,
} from 'lucide-react';

const CAMERAS = [
  { id: 'CAM-01', name: 'Bahía Carga Norte', sector: 'Logística y Despacho', workers: 2 },
  { id: 'CAM-02', name: 'Línea de Ensamble A', sector: 'Sector Maquinaria Pesada', workers: 3 },
  { id: 'CAM-03', name: 'Zona de Soldadura', sector: 'Área de Alto Riesgo', workers: 1 },
];

export default function MonitoringDashboard() {
  const [selectedCam, setSelectedCam] = useState(CAMERAS[0]);
  const [hasViolation, setHasViolation] = useState(false);
  const [currentTime, setCurrentTime] = useState('');
  const [autoSimulate, setAutoSimulate] = useState(true);
  const [confidenceScore, setConfidenceScore] = useState(99.4);

  // Live timestamp
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toTimeString().split(' ')[0]);
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Automatic simulation cycle between normal & incident
  useEffect(() => {
    if (!autoSimulate) return;
    const interval = setInterval(() => {
      setHasViolation((prev) => !prev);
      setConfidenceScore(prev => +(98.5 + Math.random() * 1.3).toFixed(1));
    }, 6000);
    return () => clearInterval(interval);
  }, [autoSimulate]);

  return (
    <div id="monitoreo" className="relative mx-auto w-full max-w-4xl">
      {/* Ambient background glow */}
      <div className={`absolute -inset-6 -z-10 rounded-3xl transition-all duration-700 blur-3xl opacity-60 ${
        hasViolation ? 'bg-rose-500/20' : 'bg-emerald-500/20'
      }`} />

      {/* Main Console Container */}
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-900/95 text-slate-100 shadow-2xl shadow-slate-950/20 backdrop-blur-xl dark:border-slate-800">
        
        {/* Top Control Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/60 px-4 py-3 sm:px-5">
          {/* Brand / Unit info */}
          <div className="flex items-center gap-3">
            <div className={`flex h-9 w-9 items-center justify-center rounded-xl transition-colors duration-300 ${
              hasViolation ? 'bg-rose-500/15 text-rose-400' : 'bg-emerald-500/15 text-emerald-400'
            }`}>
              <Activity size={18} className="animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold tracking-wider uppercase text-white">
                  Vision Edge Engine
                </span>
                <span className="rounded bg-emerald-950/80 px-1.5 py-0.5 font-mono text-[9px] font-semibold text-emerald-400 border border-emerald-800/60">
                  v2.4 RTSP
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                {selectedCam.id} · {selectedCam.sector}
              </p>
            </div>
          </div>

          {/* Camera switcher tabs */}
          <div className="flex items-center gap-1.5 rounded-lg bg-slate-900 p-1 border border-slate-800">
            {CAMERAS.map((cam) => (
              <button
                key={cam.id}
                onClick={() => setSelectedCam(cam)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-all ${
                  selectedCam.id === cam.id
                    ? 'bg-slate-800 text-emerald-400 shadow-sm border border-slate-700'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {cam.id}
              </button>
            ))}
          </div>

          {/* Live Status and Interactive Simulator Switch */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => {
                setAutoSimulate(false);
                setHasViolation(!hasViolation);
              }}
              title="Haz clic para forzar simulación de infracción o normalidad"
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-all border ${
                hasViolation
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 hover:bg-rose-500/30'
                  : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 hover:bg-emerald-500/30'
              }`}
            >
              <Sliders size={13} />
              <span>{hasViolation ? 'Simular Todo OK' : 'Simular Alerta EPP'}</span>
            </button>

            <div className="flex items-center gap-1.5 rounded-full bg-slate-950/80 px-2.5 py-1 border border-slate-800">
              <span className={`h-2 w-2 rounded-full ${hasViolation ? 'bg-rose-500 animate-ping' : 'bg-emerald-400 animate-pulse'}`} />
              <span className="text-[11px] font-bold tracking-wide uppercase text-slate-200">
                {hasViolation ? 'ALERTA ACTIVA' : 'EN VIVO'}
              </span>
            </div>
          </div>
        </div>

        {/* Video Feed Simulation Screen */}
        <div className="relative aspect-video w-full overflow-hidden bg-slate-950 select-none">
          {/* Subtle industrial CCTV grid and background */}
          <div className="absolute inset-0 bg-gradient-to-b from-slate-900/60 via-slate-950/80 to-slate-950" />

          {/* SVG Industrial Environment Mockup */}
          <svg className="absolute inset-0 h-full w-full opacity-35" preserveAspectRatio="none" viewBox="0 0 800 450">
            {/* Warehouse Racks & Beams */}
            <line x1="50" y1="40" x2="750" y2="40" stroke="#475569" strokeWidth="2" strokeDasharray="4 4" />
            <line x1="100" y1="40" x2="100" y2="380" stroke="#334155" strokeWidth="3" />
            <line x1="250" y1="40" x2="250" y2="380" stroke="#334155" strokeWidth="3" />
            <line x1="550" y1="40" x2="550" y2="380" stroke="#334155" strokeWidth="3" />
            <line x1="700" y1="40" x2="700" y2="380" stroke="#334155" strokeWidth="3" />
            {/* Shelf lines */}
            <line x1="100" y1="140" x2="250" y2="140" stroke="#1e293b" strokeWidth="4" />
            <line x1="100" y1="240" x2="250" y2="240" stroke="#1e293b" strokeWidth="4" />
            <line x1="550" y1="160" x2="700" y2="160" stroke="#1e293b" strokeWidth="4" />
            <line x1="550" y1="260" x2="700" y2="260" stroke="#1e293b" strokeWidth="4" />
            {/* Floor perspective */}
            <polygon points="0,380 800,380 800,450 0,450" fill="#0f172a" />
            <line x1="0" y1="380" x2="800" y2="380" stroke="#10b981" strokeWidth="1" opacity="0.4" />
            {/* Safety zone markings on ground */}
            <polygon points="320,400 480,400 520,440 280,440" fill="none" stroke="#eab308" strokeWidth="2" strokeDasharray="8 6" opacity="0.5" />
          </svg>

          {/* Industrial CCTV Scanlines Overlay */}
          <div className="cctv-scanlines pointer-events-none absolute inset-0 opacity-40" />

          {/* AI Scan Sweep Line */}
          <motion.div
            animate={{ y: ['0%', '100%', '0%'] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
            className={`pointer-events-none absolute inset-x-0 h-1 shadow-[0_0_15px] ${
              hasViolation 
                ? 'bg-rose-500/40 shadow-rose-500/60' 
                : 'bg-emerald-400/40 shadow-emerald-400/60'
            }`}
          />

          {/* OSD (On-Screen Display) Info Overlays */}
          <div className="absolute top-3 left-4 flex items-center gap-2 rounded bg-black/60 px-2.5 py-1 text-[10px] font-mono text-emerald-400 backdrop-blur-sm border border-emerald-500/30">
            <Video size={12} />
            <span>{selectedCam.id} · REC [30 FPS] · 1080p</span>
          </div>

          <div className="absolute top-3 right-4 flex items-center gap-2 rounded bg-black/60 px-2.5 py-1 text-[10px] font-mono text-slate-300 backdrop-blur-sm border border-slate-700">
            <span>{currentTime || '14:32:08'} UTC-3</span>
          </div>

          {/* AI Detection Targets: Worker 1 (Main Subject) */}
          <div className="absolute left-[36%] top-[20%] h-[68%] w-[28%] max-w-[200px]">
            {/* Stylized Worker Avatar (Industrial Silhouette) */}
            <div className="relative h-full w-full flex flex-col items-center justify-end pb-2">
              {/* Helmet icon/head */}
              <div className="relative flex flex-col items-center">
                {/* Safety Helmet */}
                <div className={`h-8 w-12 rounded-t-full transition-all duration-500 ${
                  hasViolation
                    ? 'bg-slate-700 opacity-60' 
                    : 'bg-yellow-400 shadow-md shadow-yellow-400/30'
                }`}>
                  <div className="mx-auto mt-1 h-1.5 w-10 rounded-sm bg-yellow-500/80" />
                </div>
                {/* Face & Safety Goggles */}
                <div className="h-6 w-9 rounded-b-md bg-amber-200/90 relative flex items-center justify-center">
                  <div className="h-2 w-7 rounded-sm bg-cyan-600/80 border border-cyan-300 shadow-sm" />
                </div>
              </div>

              {/* Safety Vest (Torso) */}
              <div className="mt-1 relative h-28 w-20 rounded-t-lg bg-orange-500 flex flex-col items-center justify-center shadow-lg border border-orange-400/50">
                {/* Reflective Stripes */}
                <div className="h-3 w-full bg-slate-100/90 my-1 shadow-sm" />
                <div className="h-3 w-full bg-slate-100/90 my-1 shadow-sm" />
                <div className="absolute inset-x-3 top-0 bottom-0 border-x-2 border-slate-100/90" />
              </div>

              {/* Work Pants & Safety Boots */}
              <div className="flex gap-1.5">
                <div className="h-24 w-8 rounded-b-md bg-blue-900 border-t border-blue-950" />
                <div className="h-24 w-8 rounded-b-md bg-blue-900 border-t border-blue-950" />
              </div>
              <div className="flex gap-2 -mt-1">
                <div className="h-4 w-9 rounded bg-stone-900 border border-stone-700" />
                <div className="h-4 w-9 rounded bg-stone-900 border border-stone-700" />
              </div>
            </div>

            {/* Main Object Bounding Box */}
            <motion.div
              animate={{
                borderColor: hasViolation ? '#f43f5e' : '#10b981',
                boxShadow: hasViolation
                  ? '0 0 20px rgba(244, 63, 94, 0.4)'
                  : '0 0 20px rgba(16, 185, 129, 0.3)',
              }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0 rounded-lg border-2 border-dashed pointer-events-none"
            >
              {/* Corner brackets */}
              <span className="absolute -top-1 -left-1 h-3 w-3 border-t-2 border-l-2 border-emerald-400" />
              <span className="absolute -top-1 -right-1 h-3 w-3 border-t-2 border-r-2 border-emerald-400" />
              <span className="absolute -bottom-1 -left-1 h-3 w-3 border-b-2 border-l-2 border-emerald-400" />
              <span className="absolute -bottom-1 -right-1 h-3 w-3 border-b-2 border-r-2 border-emerald-400" />

              {/* Top Tag */}
              <div className={`absolute -top-7 left-0 flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-[10px] font-bold tracking-wide uppercase shadow-sm border backdrop-blur-md ${
                hasViolation
                  ? 'bg-rose-500/15 border-rose-500/30 text-rose-400'
                  : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
              }`}>
                {hasViolation ? (
                  <>
                    <AlertTriangle size={11} className="text-rose-400" />
                    <span>EPP INCOMPLETO · 98.9%</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={11} className="text-emerald-400" />
                    <span>EPP CONFORME · {confidenceScore}%</span>
                  </>
                )}
              </div>

              {/* Sub-item tag: Helmet */}
              <div className={`absolute top-2 -right-28 hidden sm:flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-[9px] font-semibold shadow-sm backdrop-blur-md border ${
                hasViolation
                  ? 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                  : 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              }`}>
                <HardHat size={11} className={hasViolation ? 'text-rose-400' : 'text-emerald-400'} />
                <span>{hasViolation ? 'Falta Casco!' : 'Casco: 99.7%'}</span>
              </div>

              {/* Sub-item tag: Vest */}
              <div className="absolute top-20 -left-28 hidden sm:flex items-center gap-1.5 rounded-md bg-emerald-500/15 px-2.5 py-0.5 text-[9px] font-semibold text-emerald-300 shadow-sm backdrop-blur-md border border-emerald-500/30">
                <ShieldCheck size={11} className="text-emerald-400" />
                <span>Chaleco: 99.2%</span>
              </div>
            </motion.div>
          </div>

          {/* Second Worker in Background (Conforming) */}
          <div className="absolute right-[15%] top-[34%] h-[45%] w-[16%] opacity-75">
            <div className="relative h-full w-full flex flex-col items-center justify-end">
              <div className="h-5 w-8 rounded-t-full bg-yellow-400" />
              <div className="h-16 w-12 rounded bg-orange-500 mt-1" />
              <div className="h-14 w-10 flex gap-1">
                <div className="h-full w-4 bg-slate-800" />
                <div className="h-full w-4 bg-slate-800" />
              </div>
            </div>
            <div className="absolute inset-0 rounded border border-emerald-500/40 pointer-events-none">
              <div className="absolute -top-5 left-0 rounded-md bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-[8px] font-bold text-emerald-300 backdrop-blur-md">
                OPERARIO #02 · OK
              </div>
            </div>
          </div>

          {/* Incident Alert Banner Popup on Violation */}
          <AnimatePresence>
            {hasViolation && (
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                className="absolute bottom-6 right-6 left-6 sm:left-auto sm:right-6 flex items-center justify-between gap-5 rounded-2xl border border-rose-500/40 bg-slate-950/90 p-4 text-rose-100 shadow-2xl backdrop-blur-xl sm:max-w-md"
              >
                <div className="flex items-center gap-3.5">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose-500/15 text-rose-400 border border-rose-500/30 animate-pulse">
                    <AlertTriangle size={18} />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white">
                      Infracción detectada en tiempo real
                    </p>
                    <p className="text-[11px] text-slate-300 mt-0.5">
                      Operario #1 sin Casco Reglamentario en {selectedCam.name}.
                    </p>
                  </div>
                </div>
                <span className="shrink-0 rounded-lg bg-rose-500/15 border border-rose-500/30 px-2.5 py-1 text-[10px] font-mono font-bold text-rose-400 uppercase">
                  Alerta Enviada
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Lower Telemetry & Audit Bar */}
        <div className="grid grid-cols-2 divide-x divide-slate-800 border-t border-slate-800 bg-slate-950/80 sm:grid-cols-4">
          <div className="p-4 sm:px-5">
            <span className="text-[10px] font-medium text-slate-400">Casco de Seguridad</span>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${hasViolation ? 'bg-rose-500' : 'bg-emerald-400'}`} />
              <p className="text-xs font-bold text-white">
                {hasViolation ? 'No Detectado (0%)' : 'Detectado (99.7%)'}
              </p>
            </div>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] font-medium text-slate-400">Chaleco de Alta Visibilidad</span>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <p className="text-xs font-bold text-white">Detectado (99.2%)</p>
            </div>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] font-medium text-slate-400">Protección Ocular / Facial</span>
            <div className="mt-0.5 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <p className="text-xs font-bold text-white">Detectado (96.5%)</p>
            </div>
          </div>

          <div className="p-3 sm:px-4">
            <span className="text-[10px] font-medium text-slate-400">Latencia de Inferencia</span>
            <div className="mt-0.5 flex items-center gap-1.5 font-mono">
              <Activity size={13} className="text-emerald-400" />
              <p className="text-xs font-bold text-emerald-400">&lt; 14ms (En borde)</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
