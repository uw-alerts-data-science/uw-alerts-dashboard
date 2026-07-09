import "./globals.css";

export const metadata = {
  title: "UW Alerts",
  description: "UW Alerts live map frontend",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}