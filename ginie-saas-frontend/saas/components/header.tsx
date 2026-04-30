"use client";



import { ChevronDown, User, Database, LogOut, History, Trophy } from "lucide-react";

import { AnimatePresence, motion } from "motion/react";

import { useState, type ReactNode } from "react";

import { useAuth } from "@/lib/auth-context";



const menus = {

  products: [

    { label: "Contract Generator", description: "AI-powered DAML code generation" },

    { label: "Ledger Explorer", description: "Browse contracts and parties on Canton" },

    { label: "Security Auditor", description: "Automated compliance and vulnerability checks" },

    { label: "Party Manager", description: "Ed25519 identity and key management" },

  ],

  resources: [

    { label: "Documentation", description: "Guides and API reference" },

    { label: "Canton Network", description: "Learn about the Canton protocol" },

    { label: "DAML Docs", description: "Official DAML language reference" },

    { label: "GitHub", description: "Source code and contributions" },

  ],

};



const ease = [0.23, 1, 0.32, 1] as const;



function HamburgerIcon({ isOpen }: { isOpen: boolean }): ReactNode {

  return (

    <div className="w-8 h-4 relative flex flex-col justify-between cursor-pointer">

      <motion.span

        className="block h-0.5 w-full bg-foreground origin-center rounded-full"

        animate={isOpen ? { rotate: 45, y: 4.5 } : { rotate: 0, y: 0 }}

        transition={{ duration: 0.25, ease }}

      />

      <motion.span

        className="block h-0.5 w-full bg-foreground origin-center rounded-full"

        animate={isOpen ? { rotate: -45, y: -9.5 } : { rotate: 0, y: 0 }}

        transition={{ duration: 0.25, ease }}

      />

    </div>

  );

}



function DesktopDropdown({ 

  label, 

  menuKey, 

  isOpen, 

  onOpen, 

  onClose 

}: { 

  label: string; 

  menuKey: keyof typeof menus; 

  isOpen: boolean; 

  onOpen: () => void; 

  onClose: () => void; 

}): ReactNode {

  return (

    <div className="relative" onMouseEnter={onOpen} onMouseLeave={onClose}>

      <button 

        className="flex items-center gap-1 px-4 py-2 max-[1200px]:px-3 text-sm font-medium text-foreground/80 hover:text-foreground transition-colors rounded-full hover:bg-foreground/5"

        aria-expanded={isOpen}

        aria-haspopup="true"

      >

        {label}

        <ChevronDown className="w-4 h-4" aria-hidden="true" />

      </button>

      <AnimatePresence>

        {isOpen && (

          <motion.div

            initial={{ opacity: 0, y: 8, scale: 0.96 }}

            animate={{ opacity: 1, y: 0, scale: 1 }}

            exit={{ opacity: 0, y: 8, scale: 0.96 }}

            transition={{ duration: 0.2, ease }}

            className="absolute top-full left-0 pt-2 w-72"

          >

            <div className="bg-frame border border-border rounded-2xl shadow-lg overflow-hidden p-2">

              {menus[menuKey].map((item) => (

                <a key={item.label} href="#" className="block px-4 py-3 rounded-xl hover:bg-muted transition-colors">

                  <div className="text-sm font-medium text-foreground">{item.label}</div>

                  <div className="text-xs text-muted-foreground mt-0.5">{item.description}</div>

                </a>

              ))}

            </div>

          </motion.div>

        )}

      </AnimatePresence>

    </div>

  );

}



function MobileExpandable({ 

  label, 

  menuKey, 

  isExpanded, 

  onToggle, 

  onClose 

}: { 

  label: string; 

  menuKey: keyof typeof menus; 

  isExpanded: boolean; 

  onToggle: () => void; 

  onClose: () => void; 

}): ReactNode {

  return (

    <div className="border-b border-foreground/10">

      <button

        className="flex items-center justify-between py-4 w-full text-base font-medium text-foreground"

        onClick={onToggle}

        aria-expanded={isExpanded}

      >

        {label}

        <motion.div animate={{ rotate: isExpanded ? 180 : 0 }} transition={{ duration: 0.2 }}>

          <ChevronDown className="w-5 h-5 text-muted-foreground" aria-hidden="true" />

        </motion.div>

      </button>

      <AnimatePresence>

        {isExpanded && (

          <motion.div

            initial={{ height: 0, opacity: 0 }}

            animate={{ height: "auto", opacity: 1 }}

            exit={{ height: 0, opacity: 0 }}

            transition={{ duration: 0.2 }}

            className="overflow-hidden"

          >

            <div className="pb-2 space-y-1">

              {menus[menuKey].map((item) => (

                <a

                  key={item.label}

                  href="#"

                  className="block py-2 text-sm text-foreground/80 hover:text-foreground"

                  onClick={onClose}

                >

                  {item.label}

                </a>

              ))}

            </div>

          </motion.div>

        )}

      </AnimatePresence>

    </div>

  );

}



const CornerSVG = ({ className }: { className: string }) => (

  <svg className={className} width="50" height="50" viewBox="0 0 50 50" fill="none" aria-hidden="true">

    <path d="M5.50871e-06 0C-0.00788227 37.3001 8.99616 50.0116 50 50H5.50871e-06V0Z" fill="currentColor" />

  </svg>

);



export function Header(): ReactNode {

  const [activeMenu, setActiveMenu] = useState<string | null>(null);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [mobileExpanded, setMobileExpanded] = useState<string | null>(null);

  const { isAuthenticated, displayName, partyName, logout } = useAuth();
  const identityLabel = partyName || displayName || "Party";



  const closeMobile = () => setMobileMenuOpen(false);

  const toggleExpanded = (key: string) => setMobileExpanded(mobileExpanded === key ? null : key);



  return (

    <motion.header

      initial={{ y: -100 }}

      animate={{ y: 0 }}

      transition={{ duration: 0.5, ease }}

      className="fixed shadow-2xl/20 rounded-b-4xl top-2.5 left-1/2 -translate-x-1/2 w-full max-w-5xl max-[1200px]:max-w-2xl bg-frame z-9998 max-[850px]:top-0 max-[850px]:left-0 max-[850px]:right-0 max-[850px]:translate-x-0 max-[850px]:w-full max-[850px]:max-w-none max-[850px]:rounded-none max-[850px]:rounded-b-4xl max-[850px]:overflow-hidden"

    >

      <div className="h-20 max-[850px]:h-18 flex items-center justify-between px-4 max-[850px]:px-6">

          <a href="/" className="flex items-center gap-2 ml-4 max-[850px]:ml-0">

          <img

            src="/ginie-logo.ico"

            alt="Ginie"

            width={32}

            height={32}

            className="h-8 w-8 rounded-md"

          />

          <span style={{ fontFamily: "EB Garamond, serif" }} className="text-2xl md:text-3xl font-semibold text-accent leading-0 max-[1200px]:hidden max-[850px]:inline">
            Ginie
          </span>

        </a>



        <nav className="flex items-center gap-1 max-[1200px]:gap-0 max-[850px]:hidden">

          <DesktopDropdown

            label="Products"

            menuKey="products"

            isOpen={activeMenu === "products"}

            onOpen={() => setActiveMenu("products")}

            onClose={() => setActiveMenu(null)}

          />

          <DesktopDropdown

            label="Resources"

            menuKey="resources"

            isOpen={activeMenu === "resources"}

            onOpen={() => setActiveMenu("resources")}

            onClose={() => setActiveMenu(null)}

          />

        </nav>



        <div className="flex items-center gap-4 max-[850px]:hidden">

          {isAuthenticated && (
            <a href="/history" className="inline-flex items-center gap-1.5 rounded-full bg-foreground/5 border border-border px-3 py-1.5 text-sm font-medium text-foreground/80 hover:bg-foreground/10 transition-colors">
              <History className="w-3.5 h-3.5" />
              History
            </a>
          )}

          <a href="/leaderboard" className="inline-flex items-center gap-1.5 rounded-full bg-foreground/5 border border-border px-3 py-1.5 text-sm font-medium text-foreground/80 hover:bg-foreground/10 transition-colors">

            <Trophy className="w-3.5 h-3.5" />

            Leaderboard

          </a>

          <a href="/explorer" className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 border border-accent/20 px-3 py-1.5 text-sm font-medium text-accent hover:bg-accent/20 transition-colors">

            <Database className="w-3.5 h-3.5" />

            Ledger Explorer

          </a>

          {isAuthenticated ? (

            <div className="flex items-center gap-2">

              <a href="/profile" className="inline-flex items-center gap-1.5 rounded-full bg-accent/20 hover:bg-accent/30 px-3 py-1.5 text-sm font-medium text-foreground transition-colors" title="View profile and badges">

                <User className="w-3.5 h-3.5" />

                {identityLabel}

              </a>

              <button

                onClick={() => logout()}

                aria-label="Log out"

                className="inline-flex items-center justify-center rounded-full p-2 text-muted-foreground hover:bg-foreground/5 hover:text-foreground transition-colors"

              >

                <LogOut className="h-4 w-4" />

              </button>

            </div>

          ) : (

            <a href="/login" className="text-sm font-medium text-foreground/80 hover:text-foreground transition-colors">

              Sign in

            </a>

          )}

        </div>



        <button

          className="hidden max-[850px]:flex items-center justify-center w-10 h-10"

          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}

          aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}

          aria-expanded={mobileMenuOpen}

        >

          <HamburgerIcon isOpen={mobileMenuOpen} />

        </button>

      </div>



      <AnimatePresence>

        {mobileMenuOpen && (

          <motion.div

            initial={{ height: 0, opacity: 0 }}

            animate={{ height: "auto", opacity: 1 }}

            exit={{ height: 0, opacity: 0 }}

            transition={{ duration: 0.3, ease }}

            className="hidden max-[850px]:block overflow-hidden"

          >

            <div className="px-6 pb-4">

              <nav className="space-y-0">

                <a href="#" className="flex items-center justify-between py-4 text-base font-medium text-foreground border-b border-foreground/10" onClick={closeMobile}>

                  Customers

                </a>

                <MobileExpandable

                  label="Products"

                  menuKey="products"

                  isExpanded={mobileExpanded === "products"}

                  onToggle={() => toggleExpanded("products")}

                  onClose={closeMobile}

                />

                <MobileExpandable

                  label="Resources"

                  menuKey="resources"

                  isExpanded={mobileExpanded === "resources"}

                  onToggle={() => toggleExpanded("resources")}

                  onClose={closeMobile}

                />

              </nav>



              <div className="flex flex-col gap-3 pt-8 pb-2">

                {isAuthenticated && (
                  <a href="/history" className="inline-flex items-center gap-1.5 text-base font-medium text-foreground/80" onClick={closeMobile}>
                    <History className="w-4 h-4" />
                    History
                  </a>
                )}

                <a href="/explorer" className="inline-flex items-center gap-1.5 text-base font-medium text-accent" onClick={closeMobile}>

                  <Database className="w-4 h-4" />

                  Ledger Explorer

                </a>

                {isAuthenticated ? (

                  <span className="inline-flex items-center gap-1.5 text-base font-medium text-foreground">

                    <User className="w-4 h-4" />

                    {identityLabel}

                  </span>

                ) : (

                  <a href="/setup" className="text-base font-medium text-foreground" onClick={closeMobile}>

                    Sign in

                  </a>

                )}

              </div>

            </div>

          </motion.div>

        )}

      </AnimatePresence>



      <CornerSVG className="absolute top-0 -left-12.25 rotate-180 text-frame pointer-events-none max-[850px]:hidden" />

      <CornerSVG className="absolute top-0 -right-12.25 rotate-90 text-frame pointer-events-none max-[850px]:hidden" />

    </motion.header>

  );

}

