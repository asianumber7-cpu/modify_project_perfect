import React, { useState } from 'react';
import { X, ShieldCheck, Smartphone, Copy, CheckCircle2 } from 'lucide-react';

interface TwoFactorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function TwoFactorModal({ isOpen, onClose }: TwoFactorModalProps) {
  const [step, setStep] = useState(1); // 1: 안내, 2: QR 스캔, 3: 완료

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-2xl overflow-hidden transform transition-all scale-100 mx-4">
        
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <ShieldCheck size={18} className="text-green-500" />
            2단계 인증 설정
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* 컨텐츠 */}
        <div className="p-8 text-center min-h-[320px] flex flex-col justify-center">
          {step === 1 && (
            <div className="space-y-6 animate-fade-in-up">
              <div className="w-20 h-20 bg-green-50 dark:bg-green-900/20 rounded-full flex items-center justify-center mx-auto">
                <Smartphone size={40} className="text-green-500" />
              </div>
              <div>
                <h4 className="text-xl font-bold text-gray-900 dark:text-white mb-2">계정을 더 안전하게 보호하세요</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
                  Google OTP 또는 Authy 앱을 사용하여<br/>
                  로그인 시 추가 인증 코드를 입력하게 됩니다.
                </p>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6 animate-fade-in-up">
              <div className="bg-white p-4 rounded-xl border border-gray-200 inline-block shadow-sm">
                {/* QR 코드 플레이스홀더 (나중에 실제 QR 이미지로 교체) */}
                <div className="w-32 h-32 bg-gray-900 flex items-center justify-center text-white text-xs rounded-lg">
                  QR Code Area
                </div>
              </div>
              
              <div className="text-left bg-gray-50 dark:bg-gray-700/50 p-4 rounded-xl flex items-center justify-between border border-gray-100 dark:border-gray-700">
                <div className="overflow-hidden">
                  <p className="text-[10px] text-gray-500 uppercase font-bold mb-1">Backup Key</p>
                  <p className="text-sm font-mono font-bold text-gray-900 dark:text-white tracking-wider">ABCD 1234 EFGH</p>
                </div>
                <button 
                  onClick={() => alert('복사되었습니다!')}
                  className="p-2 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
                  title="키 복사"
                >
                  <Copy size={16} className="text-gray-500 dark:text-gray-400" />
                </button>
              </div>

              <input 
                type="text" 
                placeholder="인증 코드 6자리" 
                maxLength={6}
                className="w-full text-center px-4 py-3 rounded-xl bg-gray-50 dark:bg-gray-700 border-none focus:ring-2 focus:ring-green-500 outline-none font-bold text-lg tracking-[0.5em] text-gray-900 dark:text-white placeholder:tracking-normal placeholder:font-normal placeholder:text-sm"
              />
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 animate-fade-in-up">
              <div className="w-24 h-24 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto animate-bounce-slow">
                <CheckCircle2 size={48} className="text-green-600 dark:text-green-400" />
              </div>
              <div>
                <h4 className="text-xl font-bold text-gray-900 dark:text-white mb-2">설정이 완료되었습니다!</h4>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  이제 로그인할 때 OTP 인증이 필요합니다.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* 푸터 (버튼) */}
        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-700/30 flex justify-between items-center gap-3 border-t border-gray-100 dark:border-gray-700">
          <button 
            onClick={() => {
              if (step === 1) onClose();
              else setStep(step - 1);
            }}
            className="px-6 py-2.5 rounded-xl text-sm font-bold text-gray-500 hover:text-gray-700 hover:bg-gray-200/50 dark:text-gray-400 dark:hover:bg-gray-600 transition-colors"
          >
            {step === 1 ? '취소' : '이전'}
          </button>
          
          <button 
            onClick={() => {
              if (step < 3) setStep(step + 1);
              else onClose();
            }}
            className="px-6 py-2.5 rounded-xl bg-green-500 text-white text-sm font-bold hover:bg-green-600 shadow-lg shadow-green-200 dark:shadow-none transition-all transform active:scale-[0.98]"
          >
            {step === 3 ? '완료' : '다음 단계'}
          </button>
        </div>

      </div>
    </div>
  );
}