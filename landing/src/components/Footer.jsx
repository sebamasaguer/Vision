import React from 'react';
import { Eye, Shield, Lock, ExternalLink, Mail, Phone } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white transition-colors duration-300 dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          {/* Col 1: Brand info */}
          <div className="space-y-4">
            <a href="#inicio" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-md shadow-emerald-600/20">
                <Eye size={18} strokeWidth={2.5} />
              </div>
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                Vision<span className="text-emerald-600 dark:text-emerald-400">.ai</span>
              </span>
            </a>
            <p className="text-xs font-medium leading-relaxed text-slate-600 dark:text-slate-300">
              Plataforma de Inteligencia Artificial y Visión Computacional aplicada a la prevención de accidentes y verificación automática de EPP en tiempo real.
            </p>
            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              <Shield size={14} />
              <span>Estándares de Seguridad e Higiene Industrial</span>
            </div>
          </div>

          {/* Col 2: Soluciones */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Soluciones & Casos de Uso
            </h4>
            <ul className="mt-4 space-y-2.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              <li><a href="#monitoreo" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Detección de Casco & Chaleco</a></li>
              <li><a href="#monitoreo" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Protección Ocular y Facial</a></li>
              <li><a href="#monitoreo" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Arneses y Trabajo en Altura</a></li>
              <li><a href="#monitoreo" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Zonas de Exclusión y Maquinaria</a></li>
            </ul>
          </div>

          {/* Col 3: Empresa y Recursos */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Empresa & Compliance
            </h4>
            <ul className="mt-4 space-y-2.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              <li><a href="#mision" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Nuestra Misión</a></li>
              <li><a href="#normativas" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Auditorías y Reportes</a></li>
              <li><a href="#" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Política de Privacidad</a></li>
              <li><a href="#" className="transition-colors hover:text-emerald-700 dark:hover:text-emerald-400">Términos de Servicio</a></li>
            </ul>
          </div>

          {/* Col 4: Contacto */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Contacto Corporativo
            </h4>
            <ul className="mt-4 space-y-2.5 text-xs font-medium text-slate-600 dark:text-slate-300">
              <li className="flex items-center gap-2">
                <Mail size={13} className="text-emerald-600 dark:text-emerald-400" />
                <span>contacto@vision.ai</span>
              </li>
              <li className="flex items-center gap-2">
                <Phone size={13} className="text-emerald-600 dark:text-emerald-400" />
                <span>+54 11 5263-8800</span>
              </li>
              <li className="text-[11px] text-slate-500 dark:text-slate-400 font-normal">
                Atención a plantas industriales en toda Latinoamérica y España.
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-slate-200 pt-8 sm:flex-row dark:border-slate-800">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            © {new Date().getFullYear()} Vision Safety Systems Inc. Todos los derechos reservados.
          </p>
          <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
            <span>Privacidad de Datos Laborales</span>
            <span>·</span>
            <span>Seguridad Edge CCTV</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
