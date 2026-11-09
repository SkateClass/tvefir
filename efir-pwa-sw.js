/* ЭФИР PWA 2.1.1. Кэшируются только файлы интерфейса. */
const CACHE='efir-pwa-shell-2.1.1';
const BASE=new URL('./',self.location.href);
const SHELL=['efir-pwa.html','efir-manifest.webmanifest','efir-logo.svg','efir-icon-192.png','efir-icon-512.png','efir-icon-maskable-512.png','efir-apple-touch-icon.png','efir-pwa-offline.html'];
const ALLOWED=new Set([...SHELL,'efir-remote-home.html'].map(p=>new URL(p,BASE).pathname));
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL.map(p=>new URL(p,BASE).href))))});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(k=>k.startsWith('efir-pwa-shell-')&&k!==CACHE).map(k=>caches.delete(k)));await self.clients.claim()})())});
self.addEventListener('message',e=>{if(e.data&&e.data.type==='ACTIVATE_UPDATE')self.skipWaiting()});
self.addEventListener('fetch',e=>{const req=e.request,url=new URL(req.url);if(req.method!=='GET'||url.origin!==self.location.origin||!ALLOWED.has(url.pathname))return;
const key=url.origin+url.pathname;
e.respondWith((async()=>{const cache=await caches.open(CACHE);let timeout;const network=fetch(req).then(async response=>{if(response.ok&&response.type!=='opaque'){await cache.put(key,response.clone())}return response});e.waitUntil(network.then(()=>{}).catch(()=>{}));
try{const response=await Promise.race([network,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('timeout')),8000)})]);clearTimeout(timeout);if(response.ok)return response;const old=await cache.match(key);if(old)return old;return response}catch(err){clearTimeout(timeout);const old=await cache.match(key);if(old)return old;if(req.mode==='navigate'){const fallback=await cache.match(new URL('efir-pwa-offline.html',BASE).href);if(fallback)return fallback}return Response.error()}})())});
