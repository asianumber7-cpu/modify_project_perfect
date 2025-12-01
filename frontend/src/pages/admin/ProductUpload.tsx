import React, { useState, useRef, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, FileText, AlertCircle, CheckCircle, Image as ImageIcon, FileSpreadsheet } from 'lucide-react';
import client from '@/api/client'; // 기존 axios client 유지
import { Button } from '@/components/ui/button';

// 🚨 Tabs 설정
type UploadMode = 'image' | 'csv';

const UPLOAD_CONFIG = {
    image: {
        title: 'AI 이미지 자동 등록',
        desc: '상품 이미지를 올리면 AI가 분석하여 이름, 가격, 설명을 자동으로 생성합니다.',
        endpoint: '/products/upload/image-auto', // 백엔드 주소 (client에 baseURL이 있다면 /products...)
        accept: '.png, .jpg, .jpeg, .webp',
        label: '이미지 파일 선택',
        icon: <ImageIcon className="w-5 h-5" />
    },
    csv: {
        title: 'CSV 대량 등록',
        desc: 'CSV 파일을 사용하여 상품을 일괄 등록합니다. (이미지 URL 포함 가능)',
        endpoint: '/products/upload/csv',
        accept: '.csv',
        label: 'CSV 파일 선택',
        icon: <FileSpreadsheet className="w-5 h-5" />
    }
};

export default function ProductUpload() {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [mode, setMode] = useState<UploadMode>('image'); // 탭 상태 관리
    const [logs, setLogs] = useState<string[]>([]);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [resultCount, setResultCount] = useState({ success: 0, fail: 0 });

    const queryClient = useQueryClient();

    // 로그 추가 Helper
    const addLog = useCallback((log: string) => {
        setLogs((prev) => {
            const newLogs = prev.length >= 100 ? prev.slice(1) : prev;
            return [...newLogs, `[${new Date().toLocaleTimeString()}] ${log}`];
        });
    }, []);

    // 🚨 통합 업로드 Mutation (파일 자체를 백엔드로 전송)
    const { mutateAsync, isPending } = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);

            // 현재 탭에 맞는 엔드포인트 호출
            const config = UPLOAD_CONFIG[mode];
            
            // Content-Type을 명시하지 않아도 axios가 FormData를 감지하면 자동 설정하지만,
            // 확실하게 하기 위해 헤더를 지정할 수도 있습니다.
            const response = await client.post(config.endpoint, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                // 업로드 진행률 표시 (axios 기능)
                onUploadProgress: (progressEvent) => {
                    if (progressEvent.total) {
                        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                        setProgress(percent);
                    }
                }
            });
            return response.data;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['products'] });
            setStatus('success');
            
            // 응답 형태에 따라 결과 처리 (CSV는 통계, 이미지는 1건 성공)
            if (mode === 'csv') {
                setResultCount({ success: data.success, fail: data.failed });
                addLog(`✅ CSV Processing Complete! Success: ${data.success}, Failed: ${data.failed}`);
                if (data.errors && data.errors.length > 0) {
                    data.errors.forEach((err: string) => addLog(`❌ CSV Error: ${err}`));
                }
            } else {
                setResultCount({ success: 1, fail: 0 });
                addLog(`✅ AI Analysis & Upload Complete! Product ID: ${data.id}`);
            }
        },
        onError: (error: any) => {
            setStatus('error');
            const msg = error.response?.data?.detail || error.message;
            addLog(`❌ Upload Failed: ${msg}`);
        }
    });

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setLogs([]);
        setProgress(0);
        setStatus('idle');
        addLog(`📂 File selected (${mode.toUpperCase()}): ${file.name}`);
        addLog(`🚀 Sending to Server for processing...`);

        try {
            await mutateAsync(file);
        } catch (err) {
            // onError에서 처리됨
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const currentConfig = UPLOAD_CONFIG[mode];

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">상품 업로드 관리</h1>
            <p className="text-gray-500 mb-6">AI 자동 등록 또는 CSV 대량 등록을 선택하세요.</p>

            {/* 1. 탭 선택 UI */}
            <div className="flex space-x-4 mb-6">
                {(Object.keys(UPLOAD_CONFIG) as UploadMode[]).map((tabKey) => (
                    <button
                        key={tabKey}
                        onClick={() => { setMode(tabKey); setStatus('idle'); setLogs([]); }}
                        className={`flex items-center space-x-2 px-6 py-3 rounded-xl font-bold transition-all ${
                            mode === tabKey 
                                ? 'bg-purple-600 text-white shadow-lg shadow-purple-200 dark:shadow-none' 
                                : 'bg-white dark:bg-gray-800 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700'
                        }`}
                    >
                        {UPLOAD_CONFIG[tabKey].icon}
                        <span>{UPLOAD_CONFIG[tabKey].title}</span>
                    </button>
                ))}
            </div>

            <div className="bg-white dark:bg-gray-800 p-6 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700">
                <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        {currentConfig.icon} {currentConfig.title}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1">{currentConfig.desc}</p>
                </div>

                {/* 2. 업로드 영역 (Drag & Drop 스타일) */}
                <div 
                    className={
                        `border-2 border-dashed rounded-2xl p-12 flex flex-col items-center justify-center transition-colors min-h-[300px]
                        ${isPending 
                            ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20' 
                            : (status === 'success' ? 'border-green-500 bg-green-50 dark:bg-green-900/10' : 
                              (status === 'error' ? 'border-red-500 bg-red-50 dark:bg-red-900/10' : 'border-gray-300 dark:border-gray-600 hover:border-purple-400'))
                        }
                        ${isPending ? 'pointer-events-none' : 'cursor-pointer'}`
                    }
                    onClick={() => !isPending && fileInputRef.current?.click()}
                >
                    <input 
                        type="file" 
                        accept={currentConfig.accept} 
                        ref={fileInputRef} 
                        className="hidden" 
                        onChange={handleFileChange}
                        disabled={isPending}
                    />
                    
                    {isPending ? (
                        <div className="w-full max-w-xs text-center">
                            <div className="mb-4 text-purple-600 dark:text-purple-400 font-bold text-3xl animate-pulse">{progress}%</div>
                            <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700 overflow-hidden">
                                <div className="bg-purple-600 h-2.5 rounded-full transition-all duration-300" style={{ width: `${progress}%` }}></div>
                            </div>
                            <p className="mt-6 text-sm font-medium text-gray-600 dark:text-gray-300 animate-pulse">
                                {mode === 'image' ? '🤖 AI가 이미지를 분석 중입니다...' : '📂 데이터를 처리 중입니다...'}
                            </p>
                            {mode === 'image' && <p className="text-xs text-gray-400 mt-2">(약 3~5초 소요됩니다)</p>}
                        </div>
                    ) : (
                        <>
                            <div className={`p-5 rounded-full mb-6 ${status === 'success' ? 'bg-green-100 text-green-600' : 'bg-purple-100 text-purple-600'} dark:bg-gray-700`}>
                                {status === 'success' ? <CheckCircle size={40} /> : status === 'error' ? <AlertCircle size={40} /> : <Upload size={40} />}
                            </div>
                            <h3 className="text-xl font-bold text-gray-800 dark:text-white">
                                {status === 'success' ? '업로드 완료!' : status === 'error' ? '업로드 실패' : currentConfig.label}
                            </h3>
                            
                            {status === 'success' && (
                                <div className="mt-2 text-center">
                                    <p className="text-green-600 font-medium">작업이 성공적으로 끝났습니다.</p>
                                    <p className="text-sm text-gray-500">성공: {resultCount.success} / 실패: {resultCount.fail}</p>
                                </div>
                            )}
                            
                            {status !== 'success' && (
                                <>
                                    <p className="text-gray-500 mt-2">파일을 클릭하거나 여기로 드래그하세요.</p>
                                    <Button 
                                        type="button" 
                                        variant="default" 
                                        className="mt-6 bg-gray-900 hover:bg-black text-white"
                                    >
                                        파일 선택하기
                                    </Button>
                                </>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* 3. 로그 영역 */}
            <div className="mt-8 bg-black text-green-400 p-6 rounded-2xl font-mono text-sm h-64 overflow-y-auto shadow-xl border border-gray-800">
                <div className="sticky top-0 bg-black flex items-center gap-2 border-b border-gray-800 pb-3 mb-3 text-gray-400 z-10">
                    <FileText size={16} />
                    <span className="font-bold tracking-wider">PROCESS_LOGS</span>
                </div>
                {logs.length === 0 ? (
                    <span className="text-gray-700 animate-pulse">Waiting for input...</span>
                ) : (
                    logs.map((log, i) => <div key={i} className="mb-1 break-all hover:bg-gray-900 px-1 rounded">{log}</div>)
                )}
                <div ref={useCallback((node: HTMLDivElement | null) => { if (node) node.scrollIntoView({ behavior: 'smooth' }); }, [logs])} />
            </div>
        </div>
    );
}