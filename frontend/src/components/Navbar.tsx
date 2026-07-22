"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export default function Navbar() {
  const pathname = usePathname();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  useEffect(() => {
    setIsMenuOpen(false);
  }, [pathname]);

  return (
    <header className="site-navbar">
      <Link href="/" className="site-brand">
        UW Alerts
      </Link>

      <button
        type="button"
        className={`nav-toggle ${isMenuOpen ? "open" : ""}`}
        aria-label="Toggle navigation"
        aria-expanded={isMenuOpen}
        aria-controls="site-navigation"
        onClick={() => setIsMenuOpen((current) => !current)}
      >
        <span />
        <span />
        <span />
      </button>

      <nav
        id="site-navigation"
        className={`site-nav-links ${isMenuOpen ? "open" : ""}`}
      >
        <Link
          href="/"
          className={
            pathname === "/"
              ? "site-nav-link active"
              : "site-nav-link"
          }
        >
          Recent Alerts
        </Link>

        <Link
          href="/recent"
          className={
            pathname.startsWith("/recent")
              ? "site-nav-link active"
              : "site-nav-link"
          }
        >
          Historical View
        </Link>
      </nav>
    </header>
  );
}