# 在线书站维护

书稿只在根目录 `书稿/` 修改。网站Markdown和图表副本在构建时生成，不独立编辑，也不提交生成文件。

需要 Node 24 或更新版本。在仓库根目录运行：

```sh
npm ci --prefix site
npm test --prefix site
npm run build --prefix site
npm run check --prefix site
npm run preview --prefix site
```

本地预览访问终端显示地址下的 `/how-chinese-politics-works/` 路径。开发可运行 `npm run dev --prefix site`，正文改动后重新启动以重新生成。

构建输出为 `site/.vitepress/dist/`。31篇书稿缺失、图表缺失或章节链接无法解析时构建失败。中文索引与查询共用汉字相邻双字分词，无第三方搜索服务。

6幅正文关系图使用当前 Mermaid 源代码在构建时重绘SVG；采用与交付版相同的简化图表语法和纵向布局。不支持的图表语法会明确报错，避免漏掉关系或发布旧图。

在 GitHub Settings → Pages 将 Source 设为 **GitHub Actions**。主分支书稿、图表或网站更改会触发 `.github/workflows/pages.yml`；也可手动运行工作流。部署成功且网站可访问后，才把仓库Homepage及README阅读入口改为网站地址。

VitePress固定1.6.4，底层Vite覆盖为6.4.3，修复旧版开发服务器漏洞；锁文件随代码维护。升级依赖需重新构建并验收搜索、脚注、图表和手机阅读。

下载页目前使用真实存在的仓库交付文件。正式Release发布且附件检查通过后，可将生成脚本下载链接切换到对应Release附件。

部署不改变书稿资料截止日期、事实表述或版权声明。
