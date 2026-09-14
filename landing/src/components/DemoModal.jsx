import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  CheckCircle2,
  Sparkles,
  Building2,
  User,
  Mail,
  Phone,
  ShieldCheck,
  Loader2,
  AlertCircle,
  Cpu,
  Video,
  Activity,
} from 'lucide-react';
import emailjs from '@emailjs/browser';

export default function DemoModal({ isOpen, onClose }) {
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    company: '',
    role: 'Higiene y Seguridad (HyS)',
    cameraCount: '10 a 50 cámaras',
    notes: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage('');

    const serviceId = import.meta.env.VITE_EMAILJS_SERVICE_ID;
    const templateId = import.meta.env.VITE_EMAILJS_TEMPLATE_ID;
    const publicKey = import.meta.env.VITE_EMAILJS_PUBLIC_KEY;

    try {
      if (serviceId && templateId && publicKey) {
        const templateParams = {
          user_name: formData.name,
          user_email: formData.email,
          user_phone: formData.phone,
          phone: formData.phone,
          company: formData.company,
          role: formData.role,
          camera_count: formData.cameraCount,
          notes: formData.notes || 'Ninguna',
          submission_date: new Date().toLocaleString('es-AR'),
          name: formData.name,
          email: formData.email,
          reply_to: formData.email,
          from_name: formData.name,
          to_name: 'Equipo Vision.ai',
          message: `Solicitud de Demo para ${formData.company} (${formData.cameraCount}) - Contacto: ${formData.name} (Email: ${formData.email} | Tel: ${formData.phone || 'No especificado'})`,
        };

        await emailjs.send(
          serviceId,
          templateId,
          templateParams,
          publicKey
        );
      } else {
        await new Promise((resolve) => setTimeout(resolve, 800));
      }

      setSubmitted(true);
    } catch (error) {
      console.error('[EmailJS Error Details]:', error);
      const detail = error?.text || error?.message || 'Error de conexión';
      setErrorMessage(
        `No se pudo enviar (${detail}). Por favor intenta nuevamente o contáctanos por email.`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setSubmitted(false);
    setErrorMessage('');
    setIsLoading(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleReset}
          className="fixed inset-0 bg-slate-950/80 backdrop-blur-md"
        />

        {/* Modal Window: Ancho ampliado (max-w-2xl) */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 20 }}
          className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900 my-auto"
        >
          {/* Close button */}
          <button
            onClick={handleReset}
            disabled={isLoading}
            className="absolute top-4 right-4 z-20 flex h-9 w-9 items-center justify-center rounded-full bg-slate-900/60 text-slate-300 backdrop-blur-md transition hover:bg-slate-900 hover:text-white disabled:opacity-50 border border-slate-700/50"
            aria-label="Cerrar modal"
          >
            <X size={18} />
          </button>

          {/* ============================================================ */}
          {/* PORTADA ANIMADA CON LÍNEAS VECTORIALES Y ESCANEO TECNOLÓGICO */}
          {/* ============================================================ */}
          <div className="relative h-44 sm:h-48 w-full overflow-hidden bg-slate-950 px-6 sm:px-8 pt-7 pb-6 select-none border-b border-slate-800">
            {/* Gradientes profundos de fondo */}
            <div className="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950" />
            <div className="absolute -top-12 left-1/2 h-36 w-80 -translate-x-1/2 rounded-full bg-emerald-500/20 blur-3xl" />

            {/* Malla Vectorial Tecnológica Animada (SVG Neural Grid) */}
            <svg
              className="absolute inset-0 h-full w-full opacity-40"
              preserveAspectRatio="none"
              viewBox="0 0 600 200"
            >
              <defs>
                <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.2" />
                </linearGradient>
              </defs>

              {/* Líneas de circuito / vectores tecnológicos */}
              <path d="M 0 50 Q 150 120 300 40 T 600 90" fill="none" stroke="url(#lineGrad)" strokeWidth="1.5" strokeDasharray="6 4" />
              <path d="M 0 130 C 180 30, 420 180, 600 60" fill="none" stroke="#10b981" strokeWidth="1" opacity="0.4" />
              <path d="M 50 0 L 150 200 M 250 0 L 350 200 M 450 0 L 550 200" fill="none" stroke="#334155" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.5" />
              
              {/* Nodos interconectados */}
              <circle cx="150" cy="80" r="3.5" fill="#10b981" />
              <circle cx="300" cy="40" r="4.5" fill="#34d399" />
              <circle cx="450" cy="110" r="3.5" fill="#10b981" />
              <circle cx="220" cy="140" r="3" fill="#06b6d4" />
            </svg>

            {/* Línea de escaneo láser suave y amplia */}
            <motion.div
              animate={{ left: ['-30%', '130%'] }}
              transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
              className="pointer-events-none absolute inset-y-0 w-64 bg-gradient-to-r from-transparent via-emerald-400/25 via-teal-300/30 to-transparent skew-x-12 blur-md"
            />

            {/* Scanlines de CCTV */}
            <div className="cctv-scanlines pointer-events-none absolute inset-0 opacity-25" />

            {/* Contenido sobre la portada */}
            <div className="relative z-10 flex h-full flex-col justify-between">
              <div className="flex items-center gap-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-3 py-1 text-[11px] font-bold tracking-wider text-emerald-300 backdrop-blur-md">
                  <Cpu size={13} className="text-emerald-400 animate-pulse" />
                  <span>VISION AI · ACTIVACIÓN DE PILOTO</span>
                </div>
                <div className="hidden sm:flex items-center gap-1.5 rounded-full bg-slate-900/80 px-2.5 py-1 text-[10px] font-mono text-slate-400 border border-slate-800">
                  <Activity size={12} className="text-emerald-400" />
                  <span>DEMO EN VIVO</span>
                </div>
              </div>

              <div>
                <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                  Solicitar demostración guiada
                </h3>
                <p className="mt-1 text-xs sm:text-sm text-slate-300">
                  Coordiná una sesión técnica con un especialista para evaluar tus cámaras en planta.
                </p>
              </div>
            </div>
          </div>

          {/* ============================================================ */}
          {/* CUERPO DEL FORMULARIO                                       */}
          {/* ============================================================ */}
          <div className="p-6 sm:p-8">
            {!submitted ? (
              <div>
                {errorMessage && (
                  <div className="mb-5 flex items-center gap-2 rounded-xl bg-rose-500/10 p-3.5 text-xs text-rose-600 dark:text-rose-400 border border-rose-500/20">
                    <AlertCircle size={16} className="shrink-0" />
                    <span>{errorMessage}</span>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Grid de 2 columnas para campos */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {/* Nombre */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Nombre completo
                      </label>
                      <div className="relative mt-1.5">
                        <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          required
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          placeholder="Ing. Carlos Rodríguez"
                          className="w-full rounded-xl border border-slate-300 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-500 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:placeholder:text-slate-400 dark:focus:border-emerald-500 transition-all"
                        />
                      </div>
                    </div>

                    {/* Email */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Email Corporativo
                      </label>
                      <div className="relative mt-1.5">
                        <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="email"
                          required
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                          placeholder="crodriguez@empresa.com"
                          className="w-full rounded-xl border border-slate-300 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-500 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:placeholder:text-slate-400 dark:focus:border-emerald-500 transition-all"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {/* Teléfono / WhatsApp */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Teléfono / WhatsApp
                      </label>
                      <div className="relative mt-1.5">
                        <Phone size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="tel"
                          required
                          value={formData.phone}
                          onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                          placeholder="+54 9 11 1234-5678"
                          className="w-full rounded-xl border border-slate-300 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-500 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:placeholder:text-slate-400 dark:focus:border-emerald-500 transition-all"
                        />
                      </div>
                    </div>

                    {/* Empresa */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Empresa / Planta
                      </label>
                      <div className="relative mt-1.5">
                        <Building2 size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          required
                          value={formData.company}
                          onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                          placeholder="Siderurgia del Norte S.A."
                          className="w-full rounded-xl border border-slate-300 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-500 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:placeholder:text-slate-400 dark:focus:border-emerald-500 transition-all"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {/* Cargo */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Cargo / Área
                      </label>
                      <select
                        value={formData.role}
                        onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 py-3 px-3 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:focus:border-emerald-500 transition-all"
                      >
                        <option>Higiene y Seguridad (HyS)</option>
                        <option>Gerencia de Planta / Operaciones</option>
                        <option>Supervisión de Seguridad</option>
                        <option>IT / Infraestructura CCTV</option>
                        <option>Dirección General</option>
                      </select>
                    </div>

                    {/* Cantidad de cámaras */}
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                        Cámaras a monitorear
                      </label>
                      <select
                        value={formData.cameraCount}
                        onChange={(e) => setFormData({ ...formData, cameraCount: e.target.value })}
                        className="mt-1.5 w-full rounded-xl border border-slate-300 bg-slate-50 py-3 px-3 text-sm text-slate-900 focus:border-emerald-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 dark:border-slate-700 dark:bg-slate-800/90 dark:text-white dark:focus:border-emerald-500 transition-all"
                      >
                        <option>1 a 10 cámaras (Piloto inicial)</option>
                        <option>10 a 50 cámaras (Planta completa)</option>
                        <option>50 a 200 cámaras (Complejo industrial)</option>
                        <option>+200 cámaras (Operación Multiplanta)</option>
                      </select>
                    </div>
                  </div>

                  {/* Botón de acción */}
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="mt-6 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 py-4 text-sm font-bold text-white shadow-xl shadow-emerald-500/20 transition-all hover:from-emerald-600 hover:to-teal-700 disabled:opacity-75 active:scale-98"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 size={19} className="animate-spin" />
                        <span>Enviando solicitud de demo...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={16} />
                        <span>Confirmar Solicitud de Demostración</span>
                      </>
                    )}
                  </button>
                </form>
              </div>
            ) : (
              <div className="py-10 text-center">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-500">
                  <CheckCircle2 size={40} />
                </div>
                <h3 className="mt-5 text-2xl font-bold text-slate-900 dark:text-white">
                  ¡Solicitud Recibida con Éxito!
                </h3>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-600 dark:text-slate-300">
                  Hemos registrado la solicitud para <strong>{formData.company}</strong>. Un especialista técnico se contactará a <strong>{formData.email}</strong> para coordinar la prueba piloto.
                </p>
                <button
                  onClick={handleReset}
                  className="mt-7 rounded-xl bg-slate-900 px-7 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700"
                >
                  Entendido
                </button>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
