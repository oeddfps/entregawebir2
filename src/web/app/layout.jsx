import './globals.css';
import {GeistSans} from 'geist/font/sans';
import {GeistMono} from 'geist/font/mono';
export const metadata = { title: 'Scrapper · Centro de operaciones', description: 'Configuración y monitor del motor persistente de extracción web.' };
export default function Layout({ children }) {
  return <html lang="es" className={`${GeistSans.variable} ${GeistMono.variable}`}><body>{children}</body></html>;
}
