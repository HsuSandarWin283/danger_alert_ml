import "./globals.css";
import { AuthProvider } from "./auth-provider";
import { MicrophoneProvider } from "./lib/MicrophoneProvider";

export const metadata = {
  title: "AI Personal Safety Companion",
  description: "Danger Sound Detection System",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AuthProvider>
          <MicrophoneProvider>{children}</MicrophoneProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
