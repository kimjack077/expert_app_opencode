import { useRef, useState } from 'react'
import { Modal, Button, Space, Tag, Divider, message, Spin } from 'antd'
import { PrinterOutlined, ShareAltOutlined, FilePdfOutlined, DownloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { recordApi } from '../../services/api'

interface Props {
    open: boolean
    record: any
    onClose: () => void
}

const resultLabel: Record<string, string> = {
    pass: '合格',
    partial_pass: '基本合格',
    fail: '不合格',
}
const resultColor: Record<string, string> = {
    pass: '#22c55e',
    partial_pass: '#f59e0b',
    fail: '#ef4444',
}

function getRadioLabel(val: string) {
    const map: Record<string, string> = {
        pass: '合格',
        fail: '不合格',
        na: '不适用',
    }
    return map[val] || val
}

function flattenItems(items: any[], result: any[] = []): any[] {
    for (const item of items) {
        if (!item.is_category) result.push(item)
        if (item.children?.length) flattenItems(item.children, result)
    }
    return result
}

function normalizeUrl(url: string) {
    if (!url) return url
    url = url.replace(/\\/g, '/')
    if (url.startsWith('http')) return url
    if (!url.startsWith('/')) url = '/' + url
    return url
}

export default function InspectionReport({ open, record, onClose }: Props) {
    const reportRef = useRef<HTMLDivElement>(null)
    const [downloading, setDownloading] = useState(false)

    if (!record) return null

    const templateItems = record.template?.items || []
    const allCheckItems = flattenItems(templateItems)
    const failItems = allCheckItems.filter(
        (item: any) => item.radio_value === 'fail' || (item.score_value !== null && item.score_value !== undefined && item.pass_score && Number(item.score_value) < Number(item.pass_score))
    )
    const passItems = allCheckItems.filter((item: any) => item.radio_value === 'pass')
    const naItems = allCheckItems.filter((item: any) => item.radio_value === 'na' || item.radio_value === 'not_applicable')

    const inspectionDate = record.inspection_date
        ? dayjs(record.inspection_date).format('YYYY年MM月DD日')
        : dayjs().format('YYYY年MM月DD日')
    const inspectorName = record.inspector?.real_name || record.inspector?.full_name || record.inspector?.username || '—'

    const handlePrint = () => {
        const content = reportRef.current?.innerHTML
        if (!content) return
        const styles = `
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Noto Serif SC', 'SimSun', serif; color: #111; background: #fff; padding: 20mm 18mm; }
        .report-cover { text-align: center; padding: 24mm 0 20mm; border-bottom: 2px solid #222; margin-bottom: 10mm; }
        .report-cover h1 { font-size: 28pt; font-weight: 700; letter-spacing: 4px; margin-bottom: 6mm; }
        .report-cover .subtitle { font-size: 14pt; color: #555; }
        .section { margin-bottom: 8mm; }
        .section-title { font-size: 14pt; font-weight: 700; border-left: 4px solid #1e40af; padding-left: 8px; margin-bottom: 4mm; color: #1e40af; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 4mm; font-size: 10pt; }
        th, td { border: 1px solid #ccc; padding: 5px 8px; }
        th { background: #f0f4ff; font-weight: 600; }
        .result-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 9pt; }
        .badge-pass { background: #dcfce7; color: #16a34a; }
        .badge-fail { background: #fee2e2; color: #dc2626; }
        .badge-na { background: #f3f4f6; color: #6b7280; }
        .fail-item { margin-bottom: 6mm; border: 1px solid #fca5a5; border-radius: 6px; padding: 4mm; }
        .fail-item-title { font-weight: 700; color: #dc2626; margin-bottom: 2mm; font-size: 11pt; }
        .photos { display: flex; flex-wrap: wrap; gap: 4mm; margin-top: 3mm; }
        .photos img { width: 50mm; height: 50mm; object-fit: cover; border: 1px solid #ccc; }
        .signature-area { margin-top: 20mm; }
        .sig-row { display: flex; gap: 20mm; }
        .sig-block { flex: 1; }
        .sig-label { font-size: 10pt; color: #555; margin-bottom: 10mm; }
        .sig-line { border-bottom: 1px solid #333; padding-bottom: 2px; }
        @page { size: A4; margin: 20mm 18mm; }
        @media print { body { padding: 0; } }
      </style>
    `
        const win = window.open('', '_blank', 'width=900,height=700')
        if (!win) { message.error('无法打开打印窗口，请检查浏览器弹窗设置'); return }
        win.document.write(`<html><head><title>检查报告</title>${styles}</head><body>${content}</body></html>`)
        win.document.close()
        win.focus()
        setTimeout(() => {
            win.print()
        }, 800)
    }

    const handleShare = async () => {
        const url = window.location.href
        if (navigator.share) {
            try {
                await navigator.share({ title: `检查报告 - ${record.enterprise_name}`, url })
            } catch { /* cancelled */ }
        } else {
            await navigator.clipboard.writeText(url)
            message.success('链接已复制到剪贴板')
        }
    }

    const handleDownloadPdf = async () => {
        setDownloading(true)
        try {
            const token = localStorage.getItem('token')
            const response = await fetch(`/api/records/${record.id}/report/pdf`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            })
            if (!response.ok) throw new Error('下载失败')
            const blob = await response.blob()
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `检查报告_${record.enterprise_name || '未知'}_${dayjs().format('YYYYMMDD')}.pdf`
            document.body.appendChild(a)
            a.click()
            window.URL.revokeObjectURL(url)
            document.body.removeChild(a)
            message.success('PDF下载成功')
        } catch (error) {
            console.error('下载PDF失败:', error)
            message.error('下载PDF失败')
        } finally {
            setDownloading(false)
        }
    }

    return (
        <Modal
            title={
                <Space>
                    <FilePdfOutlined style={{ color: '#1e40af' }} />
                    <span>检查报告预览</span>
                </Space>
            }
            open={open}
            onCancel={onClose}
            width={900}
            footer={
                <Space>
                    <Button onClick={onClose}>关闭</Button>
                    <Button icon={<ShareAltOutlined />} onClick={handleShare}>分享链接</Button>
                    <Button icon={<PrinterOutlined />} onClick={handlePrint}>打印</Button>
                    <Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadPdf} loading={downloading}>
                        下载PDF
                    </Button>
                </Space>
            }
            centered
            styles={{ body: { maxHeight: '75vh', overflowY: 'auto', padding: '16px 24px' } }}
        >
            <div ref={reportRef} style={{ fontFamily: '"Noto Serif SC", SimSun, serif', color: '#111', lineHeight: 1.7 }}>

                {/* ── 封面 ── */}
                <div className="report-cover" style={{ textAlign: 'center', paddingBottom: 24, borderBottom: '2px solid #222', marginBottom: 24 }}>
                    <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: 4, marginBottom: 8 }}>现场检查报告</h1>
                    <div style={{ fontSize: 14, color: '#555' }}>
                        {record.enterprise_name || '未知企业'} &nbsp;·&nbsp; {inspectionDate}
                    </div>
                    <div style={{ marginTop: 12 }}>
                        {record.overall_result && (
                            <span style={{
                                display: 'inline-block',
                                padding: '4px 20px',
                                borderRadius: 999,
                                background: record.overall_result === 'pass' ? '#dcfce7' : record.overall_result === 'partial_pass' ? '#fef9c3' : '#fee2e2',
                                color: record.overall_result === 'pass' ? '#16a34a' : record.overall_result === 'partial_pass' ? '#a16207' : '#dc2626',
                                fontWeight: 700,
                                fontSize: 16,
                            }}>
                                总体结论：{resultLabel[record.overall_result] || record.overall_result}
                            </span>
                        )}
                    </div>
                </div>

                {/* ── 一、企业基本信息 ── */}
                <div className="section" style={{ marginBottom: 24 }}>
                    <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #1e40af', paddingLeft: 10, marginBottom: 12, color: '#1e40af' }}>
                        一、企业基本信息
                    </div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <tbody>
                            {[
                                ['企业名称', record.enterprise_name || record.enterprise?.name],
                                ['企业地址', record.enterprise?.address],
                                ['法定代表人', record.enterprise?.legal_person],
                                ['联系人', record.enterprise?.contact_person],
                                ['联系电话', record.enterprise?.contact_phone],
                                ['行业类型', record.enterprise?.enterprise_type],
                                ['风险等级', record.enterprise?.risk_level],
                                ['统一社会信用代码', record.enterprise?.credit_code],
                            ].filter(([, v]) => v).map(([label, val]) => (
                                <tr key={label as string}>
                                    <th style={{ width: '25%', background: '#f0f4ff', border: '1px solid #ccc', padding: '6px 10px', fontWeight: 600, textAlign: 'left' }}>{label}</th>
                                    <td style={{ border: '1px solid #ccc', padding: '6px 10px' }}>{val || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* ── 二、检查模板信息 ── */}
                <div className="section" style={{ marginBottom: 24 }}>
                    <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #0369a1', paddingLeft: 10, marginBottom: 12, color: '#0369a1' }}>
                        二、检查模板信息
                    </div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <tbody>
                            {[
                                ['模板名称', record.template?.name],
                                ['模板版本', record.template?.version],
                                ['检查时间', record.inspection_date ? dayjs(record.inspection_date).format('YYYY-MM-DD HH:mm') : '—'],
                                ['检查员', inspectorName],
                                ['记录状态', record.status === 'submitted' ? '已提交' : '草稿'],
                                ['总检查项', `${allCheckItems.length} 项`],
                            ].map(([label, val]) => (
                                <tr key={label as string}>
                                    <th style={{ width: '25%', background: '#f0f9ff', border: '1px solid #ccc', padding: '6px 10px', fontWeight: 600, textAlign: 'left' }}>{label}</th>
                                    <td style={{ border: '1px solid #ccc', padding: '6px 10px' }}>{val || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* ── 三、各检查项结果汇总 ── */}
                <div className="section" style={{ marginBottom: 24 }}>
                    <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #16a34a', paddingLeft: 10, marginBottom: 12, color: '#16a34a' }}>
                        三、各检查项结果汇总
                    </div>
                    {/* 统计卡片 */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
                        {[
                            { label: '合格', value: passItems.length, color: '#16a34a', bg: '#dcfce7' },
                            { label: '不合格', value: failItems.length, color: '#dc2626', bg: '#fee2e2' },
                            { label: '不适用', value: naItems.length, color: '#6b7280', bg: '#f3f4f6' },
                            { label: '总计', value: allCheckItems.length, color: '#1e40af', bg: '#eff6ff' },
                        ].map(stat => (
                            <div key={stat.label} style={{ textAlign: 'center', padding: '12px 8px', background: stat.bg, borderRadius: 8 }}>
                                <div style={{ fontSize: 28, fontWeight: 700, color: stat.color }}>{stat.value}</div>
                                <div style={{ fontSize: 12, color: '#555', marginTop: 4 }}>{stat.label}</div>
                            </div>
                        ))}
                    </div>
                    {record.template?.is_quantified && (
                        <div style={{ textAlign: 'center', padding: '8px 16px', background: '#fef9c3', borderRadius: 8, marginBottom: 12 }}>
                            <span style={{ color: '#a16207', fontWeight: 700 }}>量化总分：{record.total_score ?? 0} 分</span>
                        </div>
                    )}
                    {/* 检查明细表 */}
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                        <thead>
                            <tr>
                                <th style={{ background: '#1e40af', color: '#fff', border: '1px solid #93c5fd', padding: '7px 8px', textAlign: 'left' }}>序号</th>
                                <th style={{ background: '#1e40af', color: '#fff', border: '1px solid #93c5fd', padding: '7px 8px', textAlign: 'left' }}>检查项名称</th>
                                <th style={{ background: '#1e40af', color: '#fff', border: '1px solid #93c5fd', padding: '7px 8px' }}>检查结论</th>
                                {record.template?.is_quantified && (
                                    <th style={{ background: '#1e40af', color: '#fff', border: '1px solid #93c5fd', padding: '7px 8px' }}>得分</th>
                                )}
                                <th style={{ background: '#1e40af', color: '#fff', border: '1px solid #93c5fd', padding: '7px 8px' }}>问题描述</th>
                            </tr>
                        </thead>
                        <tbody>
                            {allCheckItems.map((item: any, idx: number) => {
                                const isOdd = idx % 2 === 0
                                const radioVal = item.radio_value
                                let badgeBg = 'transparent', badgeColor = '#555'
                                if (radioVal === 'pass') { badgeBg = '#dcfce7'; badgeColor = '#16a34a' }
                                if (radioVal === 'fail') { badgeBg = '#fee2e2'; badgeColor = '#dc2626' }
                                if (radioVal === 'na' || radioVal === 'not_applicable') { badgeBg = '#f3f4f6'; badgeColor = '#6b7280' }
                                return (
                                    <tr key={item.id} style={{ background: isOdd ? '#f8faff' : '#fff' }}>
                                        <td style={{ border: '1px solid #dde3ed', padding: '6px 8px', fontWeight: 600, width: 40 }}>{idx + 1}</td>
                                        <td style={{ border: '1px solid #dde3ed', padding: '6px 8px' }}>{item.title}</td>
                                        <td style={{ border: '1px solid #dde3ed', padding: '6px 8px', textAlign: 'center' }}>
                                            {radioVal ? (
                                                <span style={{ background: badgeBg, color: badgeColor, padding: '2px 8px', borderRadius: 4, fontWeight: 600 }}>
                                                    {getRadioLabel(radioVal)}
                                                </span>
                                            ) : item.numeric_value !== undefined && item.numeric_value !== null ? (
                                                <span>{item.numeric_value} {item.unit || ''}</span>
                                            ) : item.text_value ? (
                                                <span style={{ color: '#555' }}>已描述</span>
                                            ) : (
                                                <span style={{ color: '#bbb' }}>—</span>
                                            )}
                                        </td>
                                        {record.template?.is_quantified && (
                                            <td style={{ border: '1px solid #dde3ed', padding: '6px 8px', textAlign: 'center' }}>
                                                {item.score_value ?? '—'}
                                            </td>
                                        )}
                                        <td style={{ border: '1px solid #dde3ed', padding: '6px 8px', color: '#555', fontSize: 11 }}>
                                            {item.problem_description || '—'}
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>

                {/* ── 四、不合格项详情 ── */}
                {failItems.length > 0 && (
                    <div className="section" style={{ marginBottom: 24 }}>
                        <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #dc2626', paddingLeft: 10, marginBottom: 12, color: '#dc2626' }}>
                            四、不合格项详情
                        </div>
                        {failItems.map((item: any, idx: number) => (
                            <div key={item.id} style={{ marginBottom: 16, border: '1px solid #fca5a5', borderRadius: 8, padding: '12px 14px', background: '#fff5f5' }}>
                                <div style={{ fontWeight: 700, color: '#dc2626', marginBottom: 6, fontSize: 14 }}>
                                    {idx + 1}. {item.title}
                                </div>
                                {item.description && (
                                    <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}><b>检查内容：</b>{item.description}</div>
                                )}
                                {item.problem_description && (
                                    <div style={{ fontSize: 13, color: '#b91c1c', marginBottom: 6 }}><b>问题描述：</b>{item.problem_description}</div>
                                )}
                                {item.rectification_suggestion && (
                                    <div style={{ fontSize: 13, color: '#d97706', marginBottom: 6 }}><b>整改建议：</b>{item.rectification_suggestion}</div>
                                )}
                                {item.ai_suggestion && item.ai_suggestion !== '0' && (
                                    <div style={{ fontSize: 12, color: '#5b21b6', background: '#f5f3ff', padding: '6px 8px', borderRadius: 6, marginBottom: 6 }}>
                                        <b>AI建议：</b>{item.ai_suggestion}
                                    </div>
                                )}
                                {/* 照片 */}
                                {item.photos && item.photos.length > 0 && (
                                    <div style={{ marginTop: 10 }}>
                                        <div style={{ fontSize: 12, color: '#555', marginBottom: 6, fontWeight: 600 }}>现场照片：</div>
                                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                            {item.photos.map((url: string, pi: number) => {
                                                const src = normalizeUrl(url)
                                                return (
                                                    <img
                                                        key={pi}
                                                        src={src}
                                                        alt={`不合格项照片-${pi + 1}`}
                                                        style={{ width: 100, height: 100, objectFit: 'cover', borderRadius: 6, border: '1px solid #fca5a5', cursor: 'pointer' }}
                                                        onClick={() => window.open(src, '_blank')}
                                                    />
                                                )
                                            })}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* ── 五、整改建议 ── */}
                <div className="section" style={{ marginBottom: 24 }}>
                    <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #d97706', paddingLeft: 10, marginBottom: 12, color: '#d97706' }}>
                        {failItems.length > 0 ? '五' : '四'}、整改建议
                    </div>
                    {record.remarks ? (
                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '12px 14px', fontSize: 13, color: '#78350f', lineHeight: 1.8 }}>
                            {record.remarks}
                        </div>
                    ) : failItems.length > 0 ? (
                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '12px 14px', fontSize: 13, color: '#78350f', lineHeight: 1.8 }}>
                            {failItems.map((item: any, idx: number) => (
                                item.rectification_suggestion && (
                                    <div key={item.id} style={{ marginBottom: 8 }}>
                                        <b>{idx + 1}. {item.title}：</b>{item.rectification_suggestion}
                                    </div>
                                )
                            ))}
                            {failItems.every((item: any) => !item.rectification_suggestion) && (
                                <span style={{ color: '#9ca3af' }}>请依据检查发现的不合格项，制定相应整改措施。</span>
                            )}
                        </div>
                    ) : (
                        <div style={{ color: '#9ca3af', fontSize: 13, fontStyle: 'italic' }}>本次检查未发现不合格项，无需整改。</div>
                    )}
                </div>

                <Divider />

                {/* ── 六、签名栏 ── */}
                <div className="section signature-area" style={{ marginBottom: 8 }}>
                    <div className="section-title" style={{ fontSize: 15, fontWeight: 700, borderLeft: '4px solid #374151', paddingLeft: 10, marginBottom: 16, color: '#374151' }}>
                        {failItems.length > 0 ? '六' : '五'}、检查员签名 / 日期
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 40 }}>
                        {[
                            { label: '检查员签名', value: inspectorName },
                            { label: '检查日期', value: inspectionDate },
                            { label: '被检查单位签收', value: '' },
                            { label: '签收日期', value: '' },
                        ].map(sig => (
                            <div key={sig.label}>
                                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 30 }}>{sig.label}：</div>
                                <div style={{ borderBottom: '1px solid #374151', paddingBottom: 4, minWidth: 200, fontSize: 14, color: '#111' }}>
                                    {sig.value || '&nbsp;'}
                                </div>
                            </div>
                        ))}
                    </div>
                    <div style={{ fontSize: 11, color: '#9ca3af', textAlign: 'center', marginTop: 32 }}>
                        本报告由 易审通 (EasyAudit) 智能审核云平台自动生成 &nbsp;·&nbsp; 生成时间：{dayjs().format('YYYY-MM-DD HH:mm:ss')}
                    </div>
                </div>
            </div>
        </Modal>
    )
}
