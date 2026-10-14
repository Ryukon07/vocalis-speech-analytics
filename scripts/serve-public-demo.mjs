import { createServer, request as proxyRequest } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { randomUUID } from 'node:crypto';
const root=resolve(import.meta.dirname,'../tmp/public-demo/dist');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon'};
createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname.startsWith('/api/v1/')) {
    const upstream=proxyRequest({hostname:'127.0.0.1',port:8001,path:url.pathname+url.search,method:req.method,headers:{...req.headers,host:'127.0.0.1:8001'}},reply=>{res.writeHead(reply.statusCode,reply.headers);reply.pipe(res);});
    upstream.on('error',()=>{if(!res.headersSent)res.writeHead(502);res.end('Demo backend unavailable.');});req.pipe(upstream);return;
  }
  try{
    let path=resolve(root,'.'+decodeURIComponent(url.pathname));
    if(path!==root&&!path.startsWith(root+sep)){res.writeHead(403);res.end();return;}
    try{if(!(await stat(path)).isFile())path=resolve(root,'index.html');}catch{if(extname(path)){res.writeHead(404);res.end();return;}path=resolve(root,'index.html');}
    const headers={'Content-Type':types[extname(path)]||'application/octet-stream','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'};
    if(extname(path)==='.html'&&!/vocalis-demo-session=[a-f0-9]{32}/.test(req.headers.cookie||'')) headers['Set-Cookie']='vocalis-demo-session='+randomUUID().replaceAll('-','')+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=7200'+(req.headers['x-forwarded-proto']==='https'?'; Secure':'');
    res.writeHead(200,headers);res.end(await readFile(path));
  }catch{res.writeHead(400);res.end('Invalid request.');}
}).listen(5174,'127.0.0.1',()=>console.log('Isolated public demo proxy: http://127.0.0.1:5174'));
