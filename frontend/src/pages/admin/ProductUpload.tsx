import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle2, XCircle, Loader2, ImageIcon, Pause, Play, StopCircle, Trash2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import client from '@/api/client';

interface UploadResult {
  fileName: string;
  status: 'pending' | 'uploading' | 'success' | 'error' | 'cancelled';
  message?: string;
  productId?: number;
}

type UploadMode = 'image' | 'csv';
type UploadState = 'idle' | 'uploading' | 'paused' | 'completed';

export default function ProductUpload() {
  const [mode, setMode] = useState<UploadMode>('image');
  const [results, setResults] = useState<UploadResult[]>([]);
  const [logs, setLogs] = useState<string[]>(['Waiting for action...']);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [currentIndex, setCurrentIndex] = useState(0);
  
  // 파일 큐
  const [fileQueue, setFileQueue] = useState<File[]>([]);
  
  // 일시정지/취소 제어용 ref
  const isPausedRef = useRef(false);
  const isCancelledRef = useRef(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // 삭제 중 상태
  const [isDeleting, setIsDeleting] = useState(false);

  // 로그 자동 스크롤
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = useCallback((msg: string) => {
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    setLogs(prev => [...prev, `[${timestamp}] ${msg}`]);
  }, []);

  // =========================================================
  // 이미지 업로드 처리
  // =========================================================
  const processImageQueue = useCallback(async (files: File[], startIndex: number = 0) => {
    setUploadState('uploading');
    isPausedRef.current = false;
    isCancelledRef.current = false;

    for (let i = startIndex; i < files.length; i++) {
      // 취소 확인
      if (isCancelledRef.current) {
        addLog('⛔ 업로드가 취소되었습니다.');
        setUploadState('idle');
        return;
      }

      // 일시정지 확인
      while (isPausedRef.current) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (isCancelledRef.current) {
          addLog('⛔ 업로드가 취소되었습니다.');
          setUploadState('idle');
          return;
        }
      }

      const file = files[i];
      setCurrentIndex(i);

      // 상태를 uploading으로 변경
      setResults(prev => prev.map((r, idx) => 
        idx === i ? { ...r, status: 'uploading' } : r
      ));

      addLog(`📤 [${i + 1}/${files.length}] "${file.name}" 업로드 중...`);

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await client.post('/products/upload/image-auto', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 60000,
        });

        setResults(prev => prev.map((r, idx) => 
          idx === i ? { 
            ...r, 
            status: 'success', 
            message: `상품 ID: ${response.data.id}`,
            productId: response.data.id 
          } : r
        ));

        addLog(`✅ "${file.name}" 업로드 성공! (ID: ${response.data.id})`);

      } catch (error: any) {
        const errorMsg = error.response?.data?.detail || error.message || '알 수 없는 오류';
        
        setResults(prev => prev.map((r, idx) => 
          idx === i ? { ...r, status: 'error', message: errorMsg } : r
        ));

        addLog(`❌ "${file.name}" 업로드 실패: ${errorMsg}`);
      }
    }

    setUploadState('completed');
    addLog('🎉 모든 파일 처리가 완료되었습니다.');
  }, [addLog]);

  // =========================================================
  // Dropzone 설정
  // =========================================================
  const onDropImages = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    // 결과 초기화
    const newResults: UploadResult[] = acceptedFiles.map(file => ({
      fileName: file.name,
      status: 'pending'
    }));

    setResults(newResults);
    setFileQueue(acceptedFiles);
    setCurrentIndex(0);
    setLogs(['📁 파일이 추가되었습니다. "시작" 버튼을 눌러 업로드를 시작하세요.']);
    setUploadState('idle');
  }, []);

  const onDropCSV = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setResults([{ fileName: file.name, status: 'uploading' }]);
    addLog(`📤 CSV 파일 "${file.name}" 처리 중...`);
    setUploadState('uploading');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await client.post('/products/upload/csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });

      const { success, failed, errors } = response.data;
      
      setResults([{ 
        fileName: file.name, 
        status: failed > 0 ? 'error' : 'success',
        message: `성공: ${success}건, 실패: ${failed}건`
      }]);

      addLog(`✅ CSV 처리 완료 - 성공: ${success}건, 실패: ${failed}건`);
      
      if (errors && errors.length > 0) {
        errors.slice(0, 5).forEach((err: string) => addLog(`⚠️ ${err}`));
      }

    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message;
      setResults([{ fileName: file.name, status: 'error', message: errorMsg }]);
      addLog(`❌ CSV 처리 실패: ${errorMsg}`);
    }

    setUploadState('completed');
  }, [addLog]);

  const { getRootProps: getImageRootProps, getInputProps: getImageInputProps, isDragActive: isImageDragActive } = useDropzone({
    onDrop: onDropImages,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg', '.webp'] },
    multiple: true,
    disabled: uploadState === 'uploading'
  });

  const { getRootProps: getCSVRootProps, getInputProps: getCSVInputProps, isDragActive: isCSVDragActive } = useDropzone({
    onDrop: onDropCSV,
    accept: { 'text/csv': ['.csv'] },
    multiple: false,
    disabled: uploadState === 'uploading'
  });

  // =========================================================
  // 제어 버튼 핸들러
  // =========================================================
  const handleStart = () => {
    if (fileQueue.length === 0) {
      addLog('⚠️ 업로드할 파일이 없습니다.');
      return;
    }
    processImageQueue(fileQueue, currentIndex);
  };

  const handlePause = () => {
    isPausedRef.current = true;
    setUploadState('paused');
    addLog('⏸️ 업로드가 일시정지되었습니다.');
  };

  const handleResume = () => {
    isPausedRef.current = false;
    setUploadState('uploading');
    addLog('▶️ 업로드를 재개합니다.');
    processImageQueue(fileQueue, currentIndex);
  };

  const handleCancel = () => {
    isCancelledRef.current = true;
    isPausedRef.current = false;
    
    // 대기 중인 파일들을 cancelled로 변경
    setResults(prev => prev.map(r => 
      r.status === 'pending' || r.status === 'uploading' 
        ? { ...r, status: 'cancelled', message: '취소됨' } 
        : r
    ));
    
    setUploadState('idle');
    addLog('⛔ 업로드가 취소되었습니다.');
  };

  // =========================================================
  // 🆕 전체 삭제 (대기열 + 업로드된 상품 모두 삭제)
  // =========================================================
  const handleFullDelete = async () => {
    // 업로드 성공한 상품들의 ID 수집
    const successProductIds = results
      .filter(r => r.status === 'success' && r.productId)
      .map(r => r.productId as number);

    if (successProductIds.length === 0) {
      // 삭제할 상품이 없으면 대기열만 초기화
      handleClearQueue();
      return;
    }

    // 삭제 확인
    const confirmDelete = window.confirm(
      `업로드된 ${successProductIds.length}개 상품을 DB와 이미지에서 완전히 삭제하시겠습니까?\n\n⚠️ 이 작업은 되돌릴 수 없습니다.`
    );

    if (!confirmDelete) return;

    setIsDeleting(true);
    addLog(`🗑️ ${successProductIds.length}개 상품 삭제 시작...`);

    try {
      const response = await client.post('/products/bulk-delete', {
        product_ids: successProductIds
      });

      const { deleted_count, image_deleted_count, errors } = response.data;

      addLog(`✅ 삭제 완료: ${deleted_count}개 상품, ${image_deleted_count}개 이미지`);
      
      if (errors && errors.length > 0) {
        errors.forEach((err: string) => addLog(`⚠️ ${err}`));
      }

      // 대기열 초기화
      handleClearQueue();

    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || '삭제 실패';
      addLog(`❌ 삭제 실패: ${errorMsg}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // =========================================================
  // 대기열만 초기화 (기존 기능)
  // =========================================================
  const handleClearQueue = () => {
    setResults([]);
    setFileQueue([]);
    setCurrentIndex(0);
    setUploadState('idle');
    isPausedRef.current = false;
    isCancelledRef.current = false;
    setLogs(['🔄 대기열이 초기화되었습니다.']);
  };

  // 진행률 계산
  const completedCount = results.filter(r => r.status === 'success' || r.status === 'error' || r.status === 'cancelled').length;
  const progress = results.length > 0 ? Math.round((completedCount / results.length) * 100) : 0;

  // 업로드 성공한 상품 개수
  const successCount = results.filter(r => r.status === 'success').length;

  // 상태 아이콘 컴포넌트
  const StatusIcon = ({ status }: { status: UploadResult['status'] }) => {
    switch (status) {
      case 'success': return <CheckCircle2 className="text-green-500" size={18} />;
      case 'error': return <XCircle className="text-red-500" size={18} />;
      case 'uploading': return <Loader2 className="text-purple-500 animate-spin" size={18} />;
      case 'cancelled': return <AlertCircle className="text-orange-500" size={18} />;
      default: return <div className="w-4 h-4 rounded-full border-2 border-gray-300" />;
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* 뒤로가기 버튼 */}
      <button 
        onClick={() => window.history.back()}
        className="flex items-center gap-2 text-gray-500 hover:text-purple-600 mb-4 transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        뒤로가기
      </button>
      
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">상품 업로드 관리</h1>
      <p className="text-gray-500 mb-6">AI 자동 등록 또는 CSV 대량 등록을 선택하세요.</p>

      {/* 모드 선택 탭 */}
      <div className="flex gap-2 mb-6">
        <Button
          variant={mode === 'image' ? 'default' : 'outline'}
          onClick={() => { setMode('image'); handleClearQueue(); }}
          className="flex items-center gap-2"
          disabled={uploadState === 'uploading' || isDeleting}
        >
          <ImageIcon size={18} /> AI 이미지 자동 등록 (Bulk)
        </Button>
        <Button
          variant={mode === 'csv' ? 'default' : 'outline'}
          onClick={() => { setMode('csv'); handleClearQueue(); }}
          className="flex items-center gap-2"
          disabled={uploadState === 'uploading' || isDeleting}
        >
          <FileText size={18} /> CSV 대량 등록
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 왼쪽: 업로드 영역 */}
        <div className="space-y-4">
          {mode === 'image' ? (
            <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="font-bold text-lg mb-4 flex items-center gap-2">
                <ImageIcon className="text-purple-500" /> AI 이미지 자동 등록 (Bulk)
              </h2>

              {/* Dropzone */}
              <div
                {...getImageRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
                  ${isImageDragActive ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20' : 'border-gray-300 hover:border-purple-400'}
                  ${uploadState === 'uploading' || isDeleting ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input {...getImageInputProps()} />
                <Upload className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 dark:text-gray-300">파일을 클릭하거나 여기로 드래그하세요</p>
                <p className="text-sm text-gray-400 mt-1">.png, .jpg, .jpeg, .webp 지원</p>
              </div>

              {/* 제어 버튼 */}
              {fileQueue.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {uploadState === 'idle' && (
                    <Button onClick={handleStart} className="flex items-center gap-2 bg-green-600 hover:bg-green-700" disabled={isDeleting}>
                      <Play size={16} /> 시작
                    </Button>
                  )}
                  
                  {uploadState === 'uploading' && (
                    <Button onClick={handlePause} variant="outline" className="flex items-center gap-2">
                      <Pause size={16} /> 일시정지
                    </Button>
                  )}
                  
                  {uploadState === 'paused' && (
                    <>
                      <Button onClick={handleResume} className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700">
                        <Play size={16} /> 이어하기
                      </Button>
                      <Button onClick={handleCancel} variant="destructive" className="flex items-center gap-2">
                        <StopCircle size={16} /> 업로드 취소
                      </Button>
                    </>
                  )}
                  
                  {uploadState === 'uploading' && (
                    <Button onClick={handleCancel} variant="destructive" className="flex items-center gap-2">
                      <StopCircle size={16} /> 취소
                    </Button>
                  )}
                  
                  {/* 🆕 전체 삭제 버튼 (업로드된 상품 + 대기열 모두 삭제) */}
                  {(uploadState === 'idle' || uploadState === 'completed' || uploadState === 'paused') && (
                    <>
                      <Button onClick={handleClearQueue} variant="outline" className="flex items-center gap-2" disabled={isDeleting}>
                        <Trash2 size={16} /> 대기열 초기화
                      </Button>
                      
                      {successCount > 0 && (
                        <Button 
                          onClick={handleFullDelete} 
                          variant="destructive" 
                          className="flex items-center gap-2"
                          disabled={isDeleting}
                        >
                          {isDeleting ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Trash2 size={16} />
                          )}
                          {isDeleting ? '삭제 중...' : `전체 삭제 (${successCount}개 상품)`}
                        </Button>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* 진행률 바 */}
              {results.length > 0 && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm text-gray-500 mb-1">
                    <span>진행률</span>
                    <span>{completedCount} / {results.length} ({progress}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* 결과 목록 */}
              {results.length > 0 && (
                <div className="mt-4 max-h-[300px] overflow-y-auto space-y-2">
                  {results.map((result, index) => (
                    <div 
                      key={index} 
                      className={`flex items-center justify-between p-3 rounded-lg border
                        ${result.status === 'uploading' ? 'bg-purple-50 dark:bg-purple-900/20 border-purple-200' : ''}
                        ${result.status === 'success' ? 'bg-green-50 dark:bg-green-900/20 border-green-200' : ''}
                        ${result.status === 'error' ? 'bg-red-50 dark:bg-red-900/20 border-red-200' : ''}
                        ${result.status === 'cancelled' ? 'bg-orange-50 dark:bg-orange-900/20 border-orange-200' : ''}
                        ${result.status === 'pending' ? 'bg-gray-50 dark:bg-gray-800 border-gray-200' : ''}`}
                    >
                      <div className="flex items-center gap-3">
                        <StatusIcon status={result.status} />
                        <span className="text-sm font-medium truncate max-w-[200px]">{result.fileName}</span>
                      </div>
                      <span className="text-xs text-gray-500">{result.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="font-bold text-lg mb-4 flex items-center gap-2">
                <FileText className="text-purple-500" /> CSV 대량 등록
              </h2>

              <div
                {...getCSVRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
                  ${isCSVDragActive ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20' : 'border-gray-300 hover:border-purple-400'}
                  ${uploadState === 'uploading' ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input {...getCSVInputProps()} />
                <FileText className="w-12 h-12 mx-auto text-gray-400 mb-3" />
                <p className="text-gray-600 dark:text-gray-300">CSV 파일을 드래그하거나 클릭하세요</p>
                <p className="text-sm text-gray-400 mt-1">필수 컬럼: name, category, price</p>
              </div>

              {results.length > 0 && (
                <div className="mt-4 space-y-2">
                  {results.map((result, index) => (
                    <div key={index} className={`flex items-center justify-between p-3 rounded-lg border
                      ${result.status === 'success' ? 'bg-green-50 border-green-200' : ''}
                      ${result.status === 'error' ? 'bg-red-50 border-red-200' : ''}
                      ${result.status === 'uploading' ? 'bg-purple-50 border-purple-200' : ''}`}
                    >
                      <div className="flex items-center gap-3">
                        <StatusIcon status={result.status} />
                        <span className="text-sm font-medium">{result.fileName}</span>
                      </div>
                      <span className="text-xs text-gray-500">{result.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 오른쪽: 시스템 로그 */}
        <div className="bg-gray-900 rounded-2xl p-4 text-green-400 font-mono text-sm">
          <div className="flex items-center justify-between mb-3 text-gray-400">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="ml-2">SYSTEM_LOGS</span>
            </div>
            <span>{logs.length} logs</span>
          </div>
          
          {/* 고정 높이 + 스크롤 */}
          <div className="h-[350px] overflow-y-auto space-y-1">
            {logs.map((log, i) => (
              <div key={i} className="whitespace-pre-wrap break-words">{log}</div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}