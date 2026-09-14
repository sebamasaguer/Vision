import React, { useState } from 'react';
import { Eye, Moon, Sun, Menu, X, ShieldAlert, Sparkles, PhoneCall } from 'lucide-react';

export default function Navbar({ darkMode, toggleTheme, onOpenDemo }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  const links = [
    { label: "Monitoreo en Vivo", href: "#monitoreo" },
    { label: "Cómo Funciona", href: "#como-funciona" },
    { label: "Cumplimiento & ROI", href: "#normativas" },
    { label: "Nuestra Misión", href: "#mision" },
  ];

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl transition-colors duration-300 dark:border-slate-800/80 dark:bg-slate-950/85">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <a
          href="#inicio"
          className="group flex items-center gap-2.5"
          aria-label="Vision - IA para Seguridad Industrial"
        >
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-md shadow-emerald-500/25 transition-transform duration-300 group-hover:scale-105">
            <Eye size={22} strokeWidth={2.5} className="animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
            </span>
          </div>

          <div className="flex flex-col">
            <span className="text-xl font-bold tracking-tight text-slate-900 transition-colors dark:text-white">
              Vision<span className="text-emerald-600 dark:text-emerald-400">.ai</span>
            </span>
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">
              Safety Intelligence
            </span>
          </div>
        </a>

        {/* Desktop navigation */}
        <nav className="hidden items-center gap-7 md:flex">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-slate-600 transition-colors hover:text-emerald-700 dark:text-slate-300 dark:hover:text-emerald-400"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Action buttons */}
        <div className="flex items-center gap-2.5">
          {/* Theme Toggle Button */}
          <button
            onClick={toggleTheme}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-600 transition-all hover:border-emerald-500 hover:text-emerald-700 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-emerald-500 dark:hover:text-emerald-400"
            aria-label="Cambiar tema"
            title={darkMode ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
          >
            {darkMode ? <Sun size={17} className="text-amber-400" /> : <Moon size={17} />}
          </button>

          {/* Request Demo CTA */}
          <button
            onClick={onOpenDemo}
            className="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-emerald-500/20 transition-all duration-200 hover:from-emerald-600 hover:to-teal-700 hover:shadow-lg hover:shadow-emerald-500/30 active:scale-95 md:inline-flex"
          >
            <Sparkles size={15} />
            <span>Solicitar Demo</span>
          </button>

          {/* Mobile Menu Toggle */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-700 md:hidden dark:border-slate-800 dark:text-slate-200"
            aria-label={mobileOpen ? "Cerrar menú" : "Abrir menú"}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile menu dropdown */}
      {mobileOpen && (
        <div className="border-b border-slate-200 bg-white/95 px-5 py-5 backdrop-blur-xl md:hidden dark:border-slate-800 dark:bg-slate-950/95">
          <nav className="flex flex-col gap-3">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-900"
              >
                {link.label}
              </a>
            ))}

            <button
              onClick={() => {
                setMobileOpen(false);
                onOpenDemo();
              }}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 px-4 py-3 text-sm font-semibold text-white shadow-md shadow-emerald-500/20"
            >
              <Sparkles size={16} />
              Solicitar Demostración
            </button>
          </nav>
        </div>
      )}
    </header>
  );
}
