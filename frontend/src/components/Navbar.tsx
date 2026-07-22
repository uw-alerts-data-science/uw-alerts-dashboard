"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="site-navbar">
      <Link href="/" className="site-brand">
        UW Alerts
      </Link>

      <nav className="site-nav-links">
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