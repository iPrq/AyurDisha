export default function ToolsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="relative flex-1">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-gradient-to-b from-mint to-transparent"
      />
      <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
        {children}
      </div>
    </main>
  );
}
