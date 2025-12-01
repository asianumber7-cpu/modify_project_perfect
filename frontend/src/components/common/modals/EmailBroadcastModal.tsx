import React, { useState } from 'react';
import { X, Send, Loader2 } from 'lucide-react';
import client from '@/api/client';

interface EmailBroadcastModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const EmailBroadcastModal: React.FC<EmailBroadcastModalProps> = ({ isOpen, onClose }) => {
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSend = async () => {
    if (!subject || !body) return alert('제목과 내용을 모두 입력해주세요.');
    
    try {
      setIsLoading(true);
      // Admin API 호출
      await client.post('/api/v1/admin/broadcast-email', {
        subject,
        body,
        recipients_filter: 'all'
      });
      alert('메일 발송 요청이 시작되었습니다. (백그라운드 처리)');
      onClose();
      setSubject('');
      setBody('');
    } catch (error) {
      console.error(error);
      alert('메일 발송 요청 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Send className="w-5 h-5 text-indigo-600" />
            단체 메일 발송
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700">제목</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all"
              placeholder="공지사항 제목을 입력하세요"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-gray-700">내용 (HTML 지원)</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full h-64 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none resize-none transition-all"
              placeholder="<div>메일 내용을 입력하세요...</div>"
            />
            <p className="text-xs text-gray-500 text-right">전체 회원에게 발송됩니다.</p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 bg-gray-50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-200 rounded-lg transition-colors font-medium"
          >
            취소
          </button>
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            발송하기
          </button>
        </div>
      </div>
    </div>
  );
};

export default EmailBroadcastModal;