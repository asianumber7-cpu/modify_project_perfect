import React, { useState, useEffect } from 'react';
import { ShoppingCart, Search, RefreshCw, Eye, DollarSign, TrendingUp, Clock, X, Loader2, CheckCircle, AlertCircle, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import client from '@/api/client';

interface OrderItem {
  id: number;
  product_name: string;
  product_price: number;
  quantity: number;
  subtotal: number;
}

interface Order {
  id: number;
  order_number: string;
  user_id: number;
  user_email: string | null;
  user_name: string | null;
  status: string;
  total_amount: number;
  item_count: number;
  first_item_name: string | null;
  shipping_name: string | null;
  shipping_phone: string | null;
  created_at: string;
  items?: OrderItem[];
}

interface OrderStats {
  total_revenue: number;
  total_orders: number;
  avg_order: number;
  pending: number;
}

const STATUS_MAP: Record<string, { label: string; color: string; bgColor: string }> = {
  pending: { label: '대기중', color: 'text-yellow-700', bgColor: 'bg-yellow-100' },
  confirmed: { label: '확인됨', color: 'text-blue-700', bgColor: 'bg-blue-100' },
  shipping: { label: '배송중', color: 'text-purple-700', bgColor: 'bg-purple-100' },
  delivered: { label: '배송완료', color: 'text-green-700', bgColor: 'bg-green-100' },
  cancelled: { label: '취소됨', color: 'text-red-700', bgColor: 'bg-red-100' },
};

export default function SalesManagement() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [stats, setStats] = useState<OrderStats>({ total_revenue: 0, total_orders: 0, avg_order: 0, pending: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 필터
  const [statusFilter, setStatusFilter] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const limit = 10;

  // 모달 상태
  const [detailModal, setDetailModal] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  const statusOptions = [
    { value: 'all', label: '전체' },
    { value: 'pending', label: '대기중' },
    { value: 'confirmed', label: '확인됨' },
    { value: 'shipping', label: '배송중' },
    { value: 'delivered', label: '배송완료' },
    { value: 'cancelled', label: '취소됨' },
  ];

  // 주문 목록 조회
  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { page, limit };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await client.get('/orders/admin', { params });
      setOrders(response.data.orders || []);
      setStats(response.data.stats || { total_revenue: 0, total_orders: 0, avg_order: 0, pending: 0 });
      setTotalPages(Math.ceil((response.data.total || 0) / limit));
    } catch (err: any) {
      setError(err.response?.data?.detail || '주문 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [page, statusFilter]);

  // 필터 적용
  const handleApplyFilter = () => {
    setPage(1);
    fetchOrders();
  };

  // 상태 변경
  const handleStatusChange = async (orderId: number, newStatus: string) => {
    setActionLoading(true);
    try {
      await client.patch(`/orders/admin/${orderId}/status`, { status: newStatus });
      setActionResult({ type: 'success', message: `주문 상태가 "${STATUS_MAP[newStatus]?.label}"(으)로 변경되었습니다.` });
      fetchOrders();
      if (selectedOrder && selectedOrder.id === orderId) {
        setSelectedOrder({ ...selectedOrder, status: newStatus });
      }
      setTimeout(() => setActionResult(null), 2000);
    } catch (err: any) {
      setActionResult({ type: 'error', message: err.response?.data?.detail || '상태 변경에 실패했습니다.' });
    } finally {
      setActionLoading(false);
    }
  };

  // 상세 모달 열기
  const openDetailModal = (order: Order) => {
    setSelectedOrder(order);
    setDetailModal(true);
    setActionResult(null);
  };

  // 날짜 포맷
  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // 상태 뱃지
  const StatusBadge = ({ status }: { status: string }) => {
    const config = STATUS_MAP[status] || { label: status, color: 'text-gray-700', bgColor: 'bg-gray-100' };
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bgColor} ${config.color}`}>
        {config.label}
      </span>
    );
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
            <ShoppingCart className="text-purple-500" /> 판매 관리
          </h1>
          <p className="text-gray-500 mt-1">주문 현황 및 매출 통계</p>
        </div>
        <Button variant="outline" onClick={fetchOrders} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> 새로고침
        </Button>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white p-4 rounded-2xl">
          <div className="flex items-center gap-2 text-sm opacity-80">
            <DollarSign size={16} /> 총 매출
          </div>
          <p className="text-2xl font-bold">₩{stats.total_revenue.toLocaleString()}</p>
        </div>
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white p-4 rounded-2xl">
          <div className="flex items-center gap-2 text-sm opacity-80">
            <Package size={16} /> 총 주문
          </div>
          <p className="text-2xl font-bold">{stats.total_orders}건</p>
        </div>
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-4 rounded-2xl">
          <div className="flex items-center gap-2 text-sm opacity-80">
            <TrendingUp size={16} /> 평균 주문액
          </div>
          <p className="text-2xl font-bold">₩{stats.avg_order.toLocaleString()}</p>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white p-4 rounded-2xl">
          <div className="flex items-center gap-2 text-sm opacity-80">
            <Clock size={16} /> 처리 대기
          </div>
          <p className="text-2xl font-bold">{stats.pending}건</p>
        </div>
      </div>

      {/* 알림 */}
      {actionResult && (
        <div className={`p-4 rounded-lg mb-6 flex items-center gap-2 ${actionResult.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
          {actionResult.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
          {actionResult.message}
        </div>
      )}

      {/* 필터 */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl border p-4 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          {/* 상태 필터 */}
          <div className="flex gap-2 flex-wrap">
            {statusOptions.map(opt => (
              <Button
                key={opt.value}
                variant={statusFilter === opt.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => { setStatusFilter(opt.value); setPage(1); }}
              >
                {opt.label}
              </Button>
            ))}
          </div>

          {/* 날짜 필터 */}
          <div className="flex items-center gap-2 ml-auto">
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600"
            />
            <span className="text-gray-400">~</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600"
            />
            <Button onClick={handleApplyFilter} size="sm">적용</Button>
          </div>
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* 주문 목록 */}
      {loading ? (
        <div className="flex justify-center items-center py-20">
          <Loader2 className="animate-spin text-purple-500" size={40} />
        </div>
      ) : orders.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <ShoppingCart size={60} className="mx-auto mb-4 opacity-30" />
          <p>주문 내역이 없습니다.</p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-2xl border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">주문번호</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">고객</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">상품</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">금액</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">상태</th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-500">주문일</th>
                <th className="px-6 py-4 text-right text-sm font-medium text-gray-500">관리</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {orders.map(order => (
                <tr key={order.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4">
                    <span className="text-purple-600 font-medium">#{order.order_number.slice(-8)}</span>
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-medium">{order.user_name || order.user_email || '알 수 없음'}</p>
                    {order.user_email && order.user_name && (
                      <p className="text-xs text-gray-500">{order.user_email}</p>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-medium truncate max-w-[200px]">
                      {order.first_item_name || '상품 정보 없음'}
                      {order.item_count > 1 && <span className="text-gray-500"> 외 {order.item_count - 1}건</span>}
                    </p>
                  </td>
                  <td className="px-6 py-4 font-bold">
                    ₩{order.total_amount.toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={order.status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {formatDateTime(order.created_at)}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() => openDetailModal(order)}
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
      {detailModal && selectedOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold">주문 상세</h2>
              <button onClick={() => setDetailModal(false)}><X size={24} /></button>
            </div>

            {/* 주문 정보 */}
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-xl">
                <div>
                  <p className="text-sm text-gray-500">주문번호</p>
                  <p className="font-bold text-purple-600">#{selectedOrder.order_number}</p>
                </div>
                <StatusBadge status={selectedOrder.status} />
              </div>

              {/* 고객 정보 */}
              <div className="p-4 border rounded-xl">
                <h3 className="font-medium mb-2">고객 정보</h3>
                <p>{selectedOrder.user_name || selectedOrder.user_email || '알 수 없음'}</p>
                {selectedOrder.shipping_phone && (
                  <p className="text-sm text-gray-500">{selectedOrder.shipping_phone}</p>
                )}
              </div>

              {/* 주문 상품 */}
              <div className="p-4 border rounded-xl">
                <h3 className="font-medium mb-3">주문 상품</h3>
                {selectedOrder.items && selectedOrder.items.length > 0 ? (
                  <div className="space-y-2">
                    {selectedOrder.items.map(item => (
                      <div key={item.id} className="flex justify-between items-center py-2 border-b last:border-b-0">
                        <div>
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-sm text-gray-500">₩{item.product_price.toLocaleString()} × {item.quantity}</p>
                        </div>
                        <p className="font-bold">₩{item.subtotal.toLocaleString()}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-500">
                    {selectedOrder.first_item_name || '상품 정보 없음'}
                    {selectedOrder.item_count > 1 && ` 외 ${selectedOrder.item_count - 1}건`}
                  </p>
                )}
              </div>

              {/* 결제 금액 */}
              <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
                <div className="flex justify-between items-center">
                  <span className="font-medium">총 결제금액</span>
                  <span className="text-2xl font-bold text-purple-600">₩{selectedOrder.total_amount.toLocaleString()}</span>
                </div>
              </div>

              {/* 주문일시 */}
              <div className="text-center text-sm text-gray-500">
                주문일시: {formatDateTime(selectedOrder.created_at)}
              </div>

              {/* 상태 변경 버튼 */}
              <div className="flex gap-2 pt-4 border-t">
                {selectedOrder.status === 'pending' && (
                  <Button
                    className="flex-1"
                    onClick={() => handleStatusChange(selectedOrder.id, 'confirmed')}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 className="animate-spin" size={16} /> : '주문 확인'}
                  </Button>
                )}
                {selectedOrder.status === 'confirmed' && (
                  <Button
                    className="flex-1"
                    onClick={() => handleStatusChange(selectedOrder.id, 'shipping')}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 className="animate-spin" size={16} /> : '배송 시작'}
                  </Button>
                )}
                {selectedOrder.status === 'shipping' && (
                  <Button
                    className="flex-1 bg-green-600 hover:bg-green-700"
                    onClick={() => handleStatusChange(selectedOrder.id, 'delivered')}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 className="animate-spin" size={16} /> : '배송 완료'}
                  </Button>
                )}
                {['pending', 'confirmed'].includes(selectedOrder.status) && (
                  <Button
                    variant="destructive"
                    className="flex-1"
                    onClick={() => handleStatusChange(selectedOrder.id, 'cancelled')}
                    disabled={actionLoading}
                  >
                    {actionLoading ? <Loader2 className="animate-spin" size={16} /> : '주문 취소'}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}