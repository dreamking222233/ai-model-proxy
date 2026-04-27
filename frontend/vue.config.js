const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    host: '0.0.0.0',
    port: 8081,
    allowedHosts: 'all',
    historyApiFallback: {
      disableDotRule: true,
      htmlAcceptHeaders: ['text/html', 'application/xhtml+xml'],
      rewrites: [
        { from: /^\/api\/.*$/, to: context => context.parsedUrl.pathname },
        { from: /^\/v1\/.*$/, to: context => context.parsedUrl.pathname },
        { from: /./, to: '/index.html' },
      ],
    },
    proxy: {
      '^/api': {
        target: 'http://127.0.0.1:8085',
        changeOrigin: false,
      },
      '^/v1': {
        target: 'http://127.0.0.1:8085',
        changeOrigin: false,
      },
    },
  },
  css: {
    loaderOptions: {
      less: {
        lessOptions: {
          modifyVars: {
            'primary-color': '#667eea',
            'border-radius-base': '6px',
            'link-color': '#667eea',
          },
          javascriptEnabled: true,
        },
      },
    },
  },
})
