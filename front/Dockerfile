# ===== 第一阶段：编译构建 React =====
# node 版本和本地保持一致（本地 node -v = v24.15.0），避免两边构建行为不同。
# 原来写的 node:20 —— Node 20 已于 2026 年 4 月停止维护，不建议再用。
FROM node:24-alpine AS builder
WORKDIR /app

# npm 源同样做成构建参数：默认官方源，国内环境在 compose 里覆盖
ARG NPM_REGISTRY=https://registry.npmjs.org

# 先只拷依赖清单：只要它俩没变，这一层就命中 Docker 缓存，不用重装依赖
COPY package.json package-lock.json ./

# 用 ci 而不是 install：
#   ci 严格按 package-lock.json 安装，每次构建出来的依赖版本完全一致；
#   install 可能悄悄升级版本，导致「我这儿能跑、你那儿不行」。
# （本地已用 npm ci --dry-run 验证过 lock 文件是同步的，能装上）
RUN npm ci --registry="$NPM_REGISTRY"

# 再拷源码。注意 node_modules 已被 .dockerignore 排除 ——
# 否则这行会把宿主机（macOS/arm64）的依赖覆盖掉上面装好的 Linux 版，构建必挂。
COPY . .

RUN npm run build


# ===== 第二阶段：用 Nginx 跑静态页面 =====
# 多阶段构建的好处：最终镜像里没有 node、没有源码、没有 node_modules，
# 只有编译好的静态文件 + 一个 nginx，体积小很多。
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# 用自定义配置替换默认配置：SPA 路由回退 + 把 /api/ 反代给后端容器
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]