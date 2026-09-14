// ==UserScript==
// @name         浙大智云课堂全自动讲义资产打包导出器 (ZJU Zhiyun Lecture Exporter)
// @namespace    https://github.com/michaeltan/zju-zhiyun-exporter
// @version      1.4.0
// @description  一键抓取智云课堂高清 PPT 序列、视频切换时间戳及音视频流直链，自动打包为课程资产 ZIP，配合本地 Antigravity Skill 全自动生成图文并茂的深度讲义。
// @author       Antigravity
// @match        *://interactivemeta.cmc.zju.edu.cn/*
// @match        *://classroom.zju.edu.cn/*
// @match        *://livingroom.cmc.zju.edu.cn/*
// @match        *://onlineroom.cmc.zju.edu.cn/*
// @match        *://*.cmc.zju.edu.cn/*
// @grant        none
// @require      https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    console.log('[ZhiyunExporter v1.4.0] 启动中...');

    function timeStrToSeconds(str) {
        if (typeof str !== 'string' || !str.trim()) return null;
        const parts = str.trim().split(':');
        if (parts.length !== 2 && parts.length !== 3) return null;
        const values = parts.map(Number);
        if (values.some((v) => !Number.isFinite(v) || v < 0)) return null;
        const seconds = values[values.length - 1];
        if (seconds >= 60) return null;
        if (parts.length === 3) {
            if (values[1] >= 60) return null;
            return values[0] * 3600 + values[1] * 60 + seconds;
        }
        return values[0] * 60 + seconds;
    }

    function secToTime(sec) {
        if (typeof sec !== 'number' || !Number.isFinite(sec) || sec < 0) return null;
        const totalMs = Math.round(sec * 1000);
        const wholeSeconds = Math.floor(totalMs / 1000);
        const millis = totalMs % 1000;
        const h = Math.floor(wholeSeconds / 3600);
        const m = Math.floor((wholeSeconds % 3600) / 60);
        const s = wholeSeconds % 60;
        const suffix = millis ? `.${String(millis).padStart(3, '0').replace(/0+$/, '')}` : '';
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}${suffix}`;
    }

    function getFormattedDate() {
        const d = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
    }

    // 智能多字段提取图片直链
    function extractPptUrl(item) {
        if (!item) return '';
        if (typeof item === 'string') {
            const trimmed = item.trim();
            if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                try {
                    const parsed = JSON.parse(trimmed);
                    return extractPptUrl(parsed);
                } catch (e) {}
            }
            if (item.startsWith('http') || item.startsWith('//') || item.includes('.jpg') || item.includes('.png') || item.includes('.webp') || item.includes('cmc.zju.edu.cn')) {
                return item;
            }
            return '';
        }
        if (typeof item === 'object') {
            const keys = ['pptimgurl', 'pptthumb', 'imgSrc', 'img_src', 'picUrl', 'pic_url', 'url', 'pic', 'imageUrl', 'image_url', 'src', 'img', 'thumbnail', 'path', 'originUrl', 'snapshot'];
            for (const k of keys) {
                if (item[k] && typeof item[k] === 'string' && item[k].length > 5) return item[k];
            }
            // 深度查找任意字符串属性包含图片路径
            for (const v of Object.values(item)) {
                if (typeof v === 'string') {
                    const sub = extractPptUrl(v);
                    if (sub) return sub;
                }
            }
        }
        return '';
    }

    // 时间字段必须有明确单位。字符串时钟可直接解析；平台的 `created`
    // 已知按秒使用。其他数值字段不再通过 >10000 之类的阈值猜单位，
    // 而是保留原值并标记 unknown_numeric_unit，等待真实页面契约确认。
    function extractPptTiming(item) {
        const unknown = (field = null, rawValue = null, status = 'unknown') => ({
            timestamp: null,
            seconds: null,
            timeStatus: status,
            sourceField: field,
            rawValue: rawValue,
        });
        if (!item) return unknown();
        if (typeof item === 'string') {
            const trimmed = item.trim();
            if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                try {
                    return extractPptTiming(JSON.parse(trimmed));
                } catch (e) {
                    return unknown(null, trimmed, 'invalid_json');
                }
            }
            const seconds = timeStrToSeconds(trimmed);
            if (seconds !== null) {
                return { timestamp: secToTime(seconds), seconds, timeStatus: 'clock_string', sourceField: null, rawValue: trimmed };
            }
            return unknown(null, trimmed, 'unrecognized_string');
        }
        if (typeof item !== 'object') return unknown();

        if (typeof item.created === 'number' && Number.isFinite(item.created) && item.created >= 0) {
            return {
                timestamp: secToTime(item.created),
                seconds: item.created,
                timeStatus: 'known_seconds',
                sourceField: 'created',
                rawValue: item.created,
            };
        }

        const keys = ['switchTime', 'switch_time', 'time', 'markTime', 'mark_time', 'playTime', 'play_time', 'timeInVideo', 'pts'];
        for (const k of keys) {
            if (typeof item[k] === 'string') {
                const seconds = timeStrToSeconds(item[k]);
                if (seconds !== null) {
                    return { timestamp: secToTime(seconds), seconds, timeStatus: 'clock_string', sourceField: k, rawValue: item[k] };
                }
            }
        }
        for (const k of keys) {
            if (typeof item[k] === 'number' && Number.isFinite(item[k]) && item[k] >= 0) {
                return unknown(k, item[k], 'unknown_numeric_unit');
            }
        }
        for (const [k, v] of Object.entries(item)) {
            if (typeof v === 'string') {
                const seconds = timeStrToSeconds(v);
                if (seconds !== null) {
                    return { timestamp: secToTime(seconds), seconds, timeStatus: 'clock_string', sourceField: k, rawValue: v };
                }
            }
        }
        return unknown();
    }

    function extractPptTime(item) {
        return extractPptTiming(item).timestamp;
    }

    // 智能扫描最优 PPT 列表
    function getBestPptData() {
        let pptList = [];
        let courseName = document.title.split('-')[0].trim();
        let teacherName = '任课教师';
        let videoUrl = '';

        try {
            const video = document.querySelector('#cmc_player_video') || document.querySelector('video');
            if (video && video.src) videoUrl = video.src;

            // 1. 优先检查典型根容器
            const primarySelectors = ['.living-page-wrapper', '.course-info__main', '#cmcPlayer_container', '#app', '.ppt_container'];
            for (const sel of primarySelectors) {
                const el = document.querySelector(sel);
                if (el && el.__vue__) {
                    const v = el.__vue__;
                    if (v.courseName && courseName === '智云课程') courseName = v.courseName;
                    if (v.teacherName) teacherName = v.teacherName;
                    if (v.liveUrl && !videoUrl) videoUrl = v.liveUrl;

                    for (const prop of ['pptList', 'slideList', 'slides', 'pictureList']) {
                        if (Array.isArray(v[prop]) && v[prop].length > 0) {
                            if (extractPptUrl(v[prop][0])) {
                                pptList = v[prop];
                                break;
                            }
                        }
                    }
                }
                if (pptList.length > 0) break;
            }

            // 2. 深度遍历全页面所有 Vue 实例，筛选包含有效图片 URL 的列表
            if (pptList.length === 0) {
                const allEls = document.querySelectorAll('*');
                let candidateList = [];
                for (const el of allEls) {
                    const v = el.__vue__;
                    if (v) {
                        if (v.courseName && !courseName) courseName = v.courseName;
                        if (v.liveUrl && !videoUrl) videoUrl = v.liveUrl;

                        for (const prop of ['pptList', 'slideList', 'slides', 'pictureList']) {
                            if (Array.isArray(v[prop]) && v[prop].length > 0) {
                                const url = extractPptUrl(v[prop][0]);
                                if (url) {
                                    pptList = v[prop];
                                    break;
                                }
                                if (v[prop].length > candidateList.length) {
                                    candidateList = v[prop];
                                }
                            }
                        }
                    }
                    if (pptList.length > 0) break;
                }
                if (pptList.length === 0 && candidateList.length > 0) {
                    pptList = candidateList;
                }
            }

            // 3. 兜底方案：直接从 DOM 图片标签中抓取
            if (pptList.length === 0) {
                const domImages = document.querySelectorAll('.ppt_container img, .ppt-list img, img[src*="cmc.zju.edu.cn"], img[src*="ppt"]');
                if (domImages.length > 0) {
                    pptList = Array.from(domImages).map((img) => ({
                        imgSrc: img.src,
                        switchTime: img.getAttribute('data-time') || '00:00:00'
                    }));
                }
            }
        } catch (err) {
            console.error('[ZhiyunExporter] 扫描数据出错:', err);
        }

        return {
            pptList: pptList || [],
            courseName: courseName || '智云课程',
            teacherName: teacherName || '教师',
            videoUrl: videoUrl || ''
        };
    }

    function saveBlobToFile(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
            a.remove();
            URL.revokeObjectURL(url);
        }, 1500);
    }

    // 真正拉取高清图片 (带校验与多重降级，杜绝 14K 空图)
    async function fetchImageBlob(rawUrl, timeoutMs = 10000) {
        if (!rawUrl || typeof rawUrl !== 'string' || rawUrl.trim() === '') {
            return null;
        }
        let cleanUrl = rawUrl.trim();
        if (cleanUrl.startsWith('//')) cleanUrl = 'https:' + cleanUrl;
        else if (cleanUrl.startsWith('http://')) cleanUrl = 'https://' + cleanUrl.slice(7);

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const resp = await fetch(cleanUrl, {
                signal: controller.signal,
                mode: 'cors',
                headers: { 'Accept': 'image/*,*/*' }
            });
            clearTimeout(timer);
            if (resp.ok) {
                const b = await resp.blob();
                if (b && b.size > 2000) return b;
            }
        } catch (e) {
            clearTimeout(timer);
        }

        // 备选降级方案：创建带 crossOrigin 的 Image 走 Canvas 导出
        return new Promise((resolve) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            const failTimer = setTimeout(() => {
                img.src = '';
                resolve(null);
            }, timeoutMs);

            img.onload = () => {
                clearTimeout(failTimer);
                try {
                    const canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth || 1920;
                    canvas.height = img.naturalHeight || 1080;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    canvas.toBlob((b) => {
                        if (b && b.size > 2000) resolve(b);
                        else resolve(null);
                    }, 'image/jpeg', 0.95);
                } catch (canvasErr) {
                    resolve(null);
                }
            };
            img.onerror = () => {
                clearTimeout(failTimer);
                resolve(null);
            };
            img.src = cleanUrl;
        });
    }

    // 并发控制器
    async function runConcurrentTasks(items, limit, taskFn, onProgress) {
        const results = new Array(items.length);
        let currentIndex = 0;
        let completed = 0;

        async function worker() {
            while (currentIndex < items.length) {
                const idx = currentIndex++;
                try {
                    results[idx] = await taskFn(items[idx], idx);
                } catch (err) {
                    results[idx] = null;
                }
                completed++;
                if (onProgress) onProgress(completed, items.length);
            }
        }

        const workers = [];
        for (let i = 0; i < Math.min(limit, items.length); i++) {
            workers.push(worker());
        }
        await Promise.all(workers);
        return results;
    }

    function createExporterUI() {
        if (document.getElementById('zhiyun-exporter-panel')) return;

        const panel = document.createElement('div');
        panel.id = 'zhiyun-exporter-panel';
        panel.style.cssText = `
            position: fixed;
            top: 75px;
            right: 20px;
            z-index: 2147483647;
            background: rgba(15, 23, 42, 0.96);
            color: #f8fafc;
            border: 1px solid rgba(56, 189, 248, 0.4);
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(12px);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 13px;
            width: 270px;
            user-select: none;
            transition: all 0.3s ease;
        `;

        panel.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">
                <span style="font-weight: bold; font-size: 14px; color: #38bdf8; display: flex; align-items: center; gap: 6px;">
                    <span>🎓</span> 智云课堂讲义导出器
                </span>
                <span id="zy-close-btn" style="cursor: pointer; color: #94a3b8; font-size: 18px; line-height: 1;">×</span>
            </div>
            <div id="zy-status" style="margin-bottom: 12px; color: #94a3b8; font-size: 12px; min-height: 18px; line-height: 1.4;">
                就绪
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <button id="zy-export-zip-btn" style="background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff; border: none; border-radius: 6px; padding: 9px 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; box-shadow: 0 4px 12px rgba(37,99,235,0.3);">
                    <span>⚡ 一键打包资产包 (.zip)</span>
                </button>
                <div style="display: flex; gap: 6px;">
                    <button id="zy-copy-ppt-btn" style="flex: 1; background: rgba(255,255,255,0.08); color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 7px 8px; font-size: 12px; cursor: pointer;">
                        📋 复制 PPT 数据
                    </button>
                    <button id="zy-copy-video-btn" style="flex: 1; background: rgba(255,255,255,0.08); color: #e2e8f0; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 7px 8px; font-size: 12px; cursor: pointer;">
                        🎬 复制视频直链
                    </button>
                </div>
            </div>
            <div style="margin-top: 10px; font-size: 11px; color: #64748b; line-height: 1.4;">
                导出包保留可验证的 PPT 时间证据；未知单位不会猜测为秒/毫秒。配合 Handouter 本地整理后交给你的 Agent。
            </div>
        `;

        document.body.appendChild(panel);

        const statusEl = panel.querySelector('#zy-status');
        const exportZipBtn = panel.querySelector('#zy-export-zip-btn');
        const copyPptBtn = panel.querySelector('#zy-copy-ppt-btn');
        const copyVideoBtn = panel.querySelector('#zy-copy-video-btn');
        const closeBtn = panel.querySelector('#zy-close-btn');

        closeBtn.onclick = () => {
            panel.style.display = 'none';
        };

        function updateReadyStatus() {
            const data = getBestPptData();
            if (data.pptList && data.pptList.length > 0) {
                const sampleUrl = extractPptUrl(data.pptList[0]);
                if (sampleUrl) {
                    statusEl.textContent = `✅ 识别到《${data.courseName}》(有效 PPT ${data.pptList.length} 页)`;
                } else {
                    statusEl.textContent = `⚠️ 检测到 ${data.pptList.length} 页项，请先点右侧「<」展开 PPT 列表。`;
                }
            } else {
                statusEl.textContent = '就绪。如未检测到 PPT，请展开右侧栏。';
            }
        }
        updateReadyStatus();

        // 复制 PPT JSON 数据
        copyPptBtn.onclick = async () => {
            const data = getBestPptData();
            if (!data.pptList || data.pptList.length === 0) {
                statusEl.textContent = '❌ 未检测到 PPT 列表，请点击右侧「<」展开栏后再试。';
                return;
            }
            const res = data.pptList.map((p, i) => {
                const url = extractPptUrl(p);
                const timing = extractPptTiming(p);
                return {
                    index: i + 1,
                    timestamp: timing.timestamp,
                    seconds: timing.seconds,
                    timeStatus: timing.timeStatus,
                    sourceField: timing.sourceField,
                    rawTimeValue: timing.rawValue,
                    url: url
                };
            });
            const jsonText = JSON.stringify(res, null, 2);
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(jsonText);
            } else {
                const ta = document.createElement('textarea');
                ta.value = jsonText;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                ta.remove();
            }
            statusEl.textContent = `✅ 成功复制 ${res.length} 页 PPT 数据至剪贴板！`;
        };

        // 复制视频直链
        copyVideoBtn.onclick = async () => {
            const data = getBestPptData();
            const url = data.videoUrl || (document.querySelector('video')?.src || '');
            if (!url) {
                statusEl.textContent = '❌ 未找到视频直链，请先播放视频。';
                return;
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(url);
            }
            statusEl.textContent = '✅ 已成功将视频直链复制到剪贴板！';
        };

        // 一键打包 ZIP (并发多线程高速下载，杜绝空文件)
        exportZipBtn.onclick = async () => {
            const data = getBestPptData();
            if (!data.pptList || data.pptList.length === 0) {
                statusEl.textContent = '❌ 未定位到 PPT 数据，请展开右侧 PPT 栏。';
                return;
            }

            exportZipBtn.disabled = true;
            exportZipBtn.style.opacity = '0.6';

            try {
                if (typeof JSZip === 'undefined') {
                    throw new Error('JSZip 库加载中，请稍候点击');
                }

                const total = data.pptList.length;
                statusEl.textContent = `[*] 正在并发抓取 ${total} 页 PPT 高清图...`;

                const zip = new JSZip();
                const slidesFolder = zip.folder('slides');
                const metaList = [];

                // 准备任务
                const tasks = data.pptList.map((ppt, i) => {
                    const url = extractPptUrl(ppt);
                    const timing = extractPptTiming(ppt);
                    return {
                        index: i + 1,
                        url: url,
                        timing: timing,
                        filename: `slide_${String(i + 1).padStart(3, '0')}.jpg`
                    };
                });

                let validImageCount = 0;

                // 6 线程并发拉取图片
                await runConcurrentTasks(tasks, 6, async (task) => {
                    let downloaded = false;
                    if (task.url) {
                        const blob = await fetchImageBlob(task.url);
                        if (blob && blob.size > 2000) {
                            slidesFolder.file(task.filename, blob);
                            validImageCount++;
                            downloaded = true;
                        }
                    }
                    metaList.push({
                        index: task.index,
                        filename: task.filename,
                        timestamp: task.timing.timestamp,
                        seconds: task.timing.seconds,
                        timeStatus: task.timing.timeStatus,
                        sourceField: task.timing.sourceField,
                        rawTimeValue: task.timing.rawValue,
                        status: downloaded ? 'ok' : 'missing_image'
                    });
                }, (done, totalCount) => {
                    statusEl.textContent = `[*] 正在极速拉取 PPT [${done}/${totalCount}] (有效: ${validImageCount})...`;
                });

                metaList.sort((a, b) => a.index - b.index);
                zip.file('slides_meta.json', JSON.stringify(metaList, null, 2));

                const courseInfo = {
                    schemaVersion: 2,
                    courseName: data.courseName || '智云课程',
                    teacherName: data.teacherName || '任课教师',
                    exportDate: new Date().toISOString(),
                    totalSlides: total,
                    validImages: validImageCount,
                    missingImages: total - validImageCount,
                    unknownSlideTimes: metaList.filter((item) => item.seconds === null).length
                };
                zip.file('course_info.json', JSON.stringify(courseInfo, null, 2));

                // 签名媒体 URL 与具体回放页只放 private/，Handouter 的 Agent
                // 交接流程不会导入该目录。资产包本身仍应按私有文件保存。
                const privateSource = {
                    videoUrl: data.videoUrl || (document.querySelector('video')?.src || ''),
                    pageUrl: window.location.href
                };
                zip.folder('private').file('source.json', JSON.stringify(privateSource, null, 2));

                if (validImageCount === 0) {
                    throw new Error('未抓取到有效图片数据，请先点击右侧「<」小箭头展开 PPT 列表后再打包！');
                }

                statusEl.textContent = '📦 正在压缩生成资产包...';
                const zipContent = await zip.generateAsync({
                    type: 'blob',
                    compression: 'DEFLATE',
                    compressionOptions: { level: 6 }
                });

                const safeName = courseInfo.courseName.replace(/[\\/:*?"<>|]/g, '_');
                const zipFilename = `${safeName}_${getFormattedDate()}_资产包.zip`;

                saveBlobToFile(zipContent, zipFilename);
                const unknownTimes = metaList.filter((item) => item.seconds === null).length;
                statusEl.textContent = `🎉 打包完成：PPT ${validImageCount}/${total} 张，未知时间 ${unknownTimes} 条。资产包含 private/ 来源信息，请仅本地保存。`;
            } catch (err) {
                console.error(err);
                statusEl.textContent = `❌ ${err.message}`;
            } finally {
                exportZipBtn.disabled = false;
                exportZipBtn.style.opacity = '1';
            }
        };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createExporterUI);
    } else {
        createExporterUI();
    }
    setTimeout(createExporterUI, 1500);

})();
