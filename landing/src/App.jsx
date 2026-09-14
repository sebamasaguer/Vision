import React, { useState } from 'react';
import { useTheme } from './hooks/useTheme';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import ROISection from './components/ROISection';
import Mission from './components/Mission';
import CTASection from './components/CTASection';
import Footer from './components/Footer';
import DemoModal from './components/DemoModal';

export default function App() {
  const { darkMode, toggleTheme } = useTheme();
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);

  const handleOpenDemo = () => setIsDemoModalOpen(true);
  const handleCloseDemo = () => setIsDemoModalOpen(false);

  return (
    <div className="min-h-screen bg-white text-slate-900 transition-colors duration-300 dark:bg-slate-950 dark:text-slate-100">
      {/* Top sticky navigation */}
      <Navbar
        darkMode={darkMode}
        toggleTheme={toggleTheme}
        onOpenDemo={handleOpenDemo}
      />

      {/* Main landing content */}
      <main>
        <Hero onOpenDemo={handleOpenDemo} />
        <Features />
        <ROISection onOpenDemo={handleOpenDemo} />
        <Mission />
        <CTASection onOpenDemo={handleOpenDemo} />
      </main>

      {/* Footer */}
      <Footer />

      {/* Lead Capture / Pilot Request Modal */}
      <DemoModal
        isOpen={isDemoModalOpen}
        onClose={handleCloseDemo}
      />
    </div>
  );
}
