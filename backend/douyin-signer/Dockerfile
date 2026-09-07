FROM node:24-alpine

WORKDIR /app

ENV NODE_ENV=production \
    PORT=8787

COPY server.js ./server.js
COPY sign_once.js ./sign_once.js
COPY vendor ./vendor

USER node

EXPOSE 8787

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=4 \
    CMD ["node", "-e", "const http=require('http'); const port=process.env.PORT||'8787'; const request=http.get({host:'127.0.0.1',port,path:'/health',timeout:2000}, response=>process.exit(response.statusCode===200?0:1)); request.on('error',()=>process.exit(1)); request.on('timeout',()=>{request.destroy();process.exit(1)});"]

CMD ["node", "server.js"]
