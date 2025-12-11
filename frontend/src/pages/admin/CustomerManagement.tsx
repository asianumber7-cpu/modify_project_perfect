import React, { useState, useEffect } from 'react';
import { Users, Search, RefreshCw, Eye, UserCheck, UserX, Shield, ShieldOff, Loader2, CheckCircle, AlertCircle, X, Mail, Phone, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import client from '@/api/client';

interface User {
  id: number;
  email: string;
  full_name: string | null;
  phone_number: string | null;
  provider: string;
  is_active: boolean;
  is_superuser: boolean;
  is_marketing_agreed: boolean;
  created_at: string;
  updated_at: string;
}

interface UserStats {
  total: number;
  active: number;
  marketing: number;
  admin: number;
}

export default function CustomerManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<UserStats>({ total: 0, active: 0, marketing: 0, admin: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 검색/필터
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const limit = 10;

  // 모달 상태
  const [detailModal, setDetailModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  // 회원 목록 조회
  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { page, limit };
      if (search) params.search = search;
      if (activeFilter !== 'all') params.is_active = activeFilter === 'active';

      const response = await client.get('/users/admin/list', { params });
      setUsers(response.data.users || []);
      setStats(response.data.stats || { total: 0, active: 0, marketing: 0, admin: 0 });
      setTotalPages(Math.ceil((response.data.total || 0) / limit));
    } catch (err: any) {
      setError(err.response?.data?.detail || '회원 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, activeFilter]);

  // 검색 실행
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchUsers();
  };

  // 상태 변경
  const handleStatusChange = async (userId: number, isActive: boolean) => {
    setActionLoading(true);
    try {
      await client.patch(`/users/admin/${userId}/status`, { is_active: isActive });
      setActionResult({ type: 'success', message: isActive ? '회원이 활성화되었습니다.' : '회원이 비활성화되었습니다.' });
      fetchUsers();
      setTimeout(() => setActionResult(null), 2000);
    } catch (err: any) {
      setActionResult({ type: 'error', message: err.response?.data?.detail || '상태 변경에 실패했습니다.' });
    } finally {
      setActionLoading(false);
    }
  };

  // 관리자 권한 변경
  const handleAdminToggle = async (userId: number, isSuperuser: boolean) => {
    setActionLoading(true);
    try {
      await client.patch(`/users/admin/${userId}/status`, { is_superuser: isSuperuser });
      setActionResult({ type: 'success', message: isSuperuser ? '관리자 권한이 부여되었습니다.' : '관리자 권한이 해제되었습니다.' });
      fetchUsers();
      if (selectedUser && selectedUser.id === userId) {
        setSelectedUser({ ...selectedUser, is_superuser: isSuperuser });
      }
      setTimeout(() => setActionResult(null), 2000);
    } catch (err: any) {
      setActionResult({ type: 'error', message: err.response?.data?.detail || '권한 변경에 실패했습니다.' });
    } finally {
      setActionLoading(false);
    }
  };

  // 상세 모달 열기
  const openDetailModal = (user: User) => {
    setSelectedUser(user);
    setDetailModal(true);
    setActionResult(null);
  };

  // 날짜 포맷
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* 뒤로가기 버튼 */}
      <button 
        onClick={() => window.history.back()}
        className="flex items-center gap-2 text-gray-500 hover:text-purple-600 mb-4 transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        뒤로가기
      </button>

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
            <Users className="text-purple-500" /> 고객 관리
          </h1>
          <p className="text-gray-500 mt-1">회원 정보 조회 및 관리</p>
        </div>
        <Button variant="outline" onClick={fetchUsers} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> 새로고침
        </Button>
      </div>

      {/* 검색 */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl border p-4 mb-6">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              placeholder="이메일 또는 이름으로 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:outline-none dark:bg-gray-700 dark:border-gray-600"
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={activeFilter === 'all' ? 'default' : 'outline'}
              onClick={() => { setActiveFilter('all'); setPage(1); }}
            >
              전체
            </Button>
            <Button
              type="button"
              variant={activeFilter === 'active' ? 'default' : 'outline'}
              onClick={() => { setActiveFilter('active'); setPage(1); }}
            >
              활성
            </Button>
            <Button
              type="button"
              variant={activeFilter === 'inactive' ? 'default' : 'outline'}
              onClick={() => { setActiveFilter('inactive'); setPage(1); }}
            >
              비활성
            </Button>
          </div>
        </form>
      </div>

      {/* 알림 */}
      {actionResult && (
        <div className={`p-4 rounded-lg mb-6 flex items-center gap-2 ${actionResult.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
          {actionResult.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
          {actionResult.message}
        </div>
      )}

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">전체 회원</p>
          <p className="text-2xl font-bold">{stats.total}</p>
        </div>
        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">활성 회원</p>
          <p className="text-2xl font-bold">{stats.active}</p>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">마케팅 동의</p>
          <p className="text-2xl font-bold">{stats.marketing}</p>
        </div>
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">관리자</p>
          <p className="text-2xl font-bold">{stats.admin}</p>
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* 회원 목록 테이블 */}
      {loading ? (
        <div className="flex justify-center items-center py-20">
          <Loader2 className="animate-spin text-purple-500" size={40} />
        </div>
      ) : users.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Users size={60} className="mx-auto mb-4 opacity-30" />
          <p>등록된 회원이 없습니다.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-2xl border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">회원</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">상태</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">가입일</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">권한</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-gray-500">관리</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {users.map(user => (
                <tr key={user.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium">{user.full_name || '이름 없음'}</p>
                      <p className="text-sm text-gray-500">{user.email}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium
                      ${user.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                      {user.is_active ? <UserCheck size={12} /> : <UserX size={12} />}
                      {user.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-6 py-4">
                    {user.is_superuser ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                        <Shield size={12} /> 관리자
                      </span>
                    ) : (
                      <span className="text-sm text-gray-500">일반 회원</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => openDetailModal(user)}
                      className="p-2 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors"
                    >
                      <Eye size={18} className="text-gray-500" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-8">
          <Button variant="outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>이전</Button>
          <span className="px-4 text-gray-600">{page} / {totalPages}</span>
          <Button variant="outline" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>다음</Button>
        </div>
      )}

      {/* 상세 모달 */}
      {detailModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">회원 상세 정보</h2>
              <button onClick={() => setDetailModal(false)}><X size={24} /></button>
            </div>

            <div className="space-y-4">
              {/* 프로필 */}
              <div className="flex items-center gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-xl">
                <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center">
                  <Users className="text-purple-500" size={28} />
                </div>
                <div>
                  <p className="font-bold text-lg">{selectedUser.full_name || '이름 없음'}</p>
                  <p className="text-sm text-gray-500">{selectedUser.provider} 가입</p>
                </div>
              </div>

              {/* 정보 */}
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Mail className="text-gray-400" size={18} />
                  <span>{selectedUser.email}</span>
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Phone className="text-gray-400" size={18} />
                  <span>{selectedUser.phone_number || '전화번호 없음'}</span>
                </div>
                <div className="flex items-center gap-3 p-3 border rounded-lg">
                  <Calendar className="text-gray-400" size={18} />
                  <span>가입일: {formatDate(selectedUser.created_at)}</span>
                </div>
              </div>

              {/* 상태 뱃지 */}
              <div className="flex flex-wrap gap-2">
                <span className={`px-3 py-1 rounded-full text-sm ${selectedUser.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                  {selectedUser.is_active ? '✓ 활성' : '✗ 비활성'}
                </span>
                <span className={`px-3 py-1 rounded-full text-sm ${selectedUser.is_marketing_agreed ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}>
                  {selectedUser.is_marketing_agreed ? '✓ 마케팅 동의' : '✗ 마케팅 거부'}
                </span>
                {selectedUser.is_superuser && (
                  <span className="px-3 py-1 rounded-full text-sm bg-purple-100 text-purple-700">
                    👑 관리자
                  </span>
                )}
              </div>

              {/* 액션 버튼 */}
              <div className="flex gap-2 pt-4 border-t">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => handleStatusChange(selectedUser.id, !selectedUser.is_active)}
                  disabled={actionLoading}
                >
                  {selectedUser.is_active ? (
                    <><UserX size={16} className="mr-2" /> 비활성화</>
                  ) : (
                    <><UserCheck size={16} className="mr-2" /> 활성화</>
                  )}
                </Button>
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => handleAdminToggle(selectedUser.id, !selectedUser.is_superuser)}
                  disabled={actionLoading}
                >
                  {selectedUser.is_superuser ? (
                    <><ShieldOff size={16} className="mr-2" /> 권한 해제</>
                  ) : (
                    <><Shield size={16} className="mr-2" /> 관리자 부여</>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}