import type { Metadata } from 'next';
import './globals.css';
import Providers from '../components/Providers';
import Layout from '../components/Layout';

export const metadata: Metadata = {
  title: 'PRAVAH Command Center',
  description: 'AI Infrastructure Governance & Operational Visibility Console',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Providers>
          <Layout>{children}</Layout>
        </Providers>
      </body>
    </html>
  );
}
