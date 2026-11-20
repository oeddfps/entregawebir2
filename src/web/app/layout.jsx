import './globals.css';
import {GeistSans} from 'geist/font/sans';
import {GeistMono} from 'geist/font/mono';
export const metadata = { title: 'Scrapper · Centro de operaciones', description: 'Configuración y monitor del motor persistente de extracción web.' };
const themeScript = `(function(){var theme;try{theme=localStorage.getItem('scrapper-theme')}catch(e){}var dark=theme==='dark'||(theme!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);var root=document.documentElement;root.dataset.theme=dark?'dark':'light';root.classList.toggle('dark',dark);root.style.colorScheme=dark?'dark':'light'})()`;
export default function Layout({ children }) {
  return <html lang="es" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}><head><script dangerouslySetInnerHTML={{__html:themeScript}}/></head><body>{children}</body></html>;
}
