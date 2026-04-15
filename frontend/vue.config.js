const { defineConfig } = require('@vue/cli-service')
module.exports = defineConfig({
  transpileDependencies: true,
  devServer: {
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8085',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://127.0.0.1:8085',
        changeOrigin: true,
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
