import React, { useState, useEffect } from 'react';
import { Package, Search, Filter, Edit2, Trash2, Eye, RefreshCw, Plus, X, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import client from '@/api/client';

interface Product {
  id: number;
  name: string;
  description: string;
  price: number;
  stock_quantity: number;
  category: string;
  gender: string;
  image_url: string;
  created_at: string;
}

interface ProductStats {
  total: number;
  selling: number;
  soldout: number;
  avg_price: number;
}

// ✅ 백엔드 API URL (환경변수 또는 기본값)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ✅ 이미지 URL 변환 함수
const getImageUrl = (imageUrl: string | null | undefined): string => {
  if (!imageUrl) {
    return 'https://placehold.co/400x400?text=No+Image';
  }
  
  // 이미 전체 URL인 경우 그대로 반환
  if (imageUrl.startsWith('http://') || imageUrl.startsWith('https://')) {
    return imageUrl;
  }
  
  // /static/images/... 형식이면 백엔드 URL 붙이기
  if (imageUrl.startsWith('/static/')) {
    return `${API_BASE_URL}${imageUrl}`;
  }
  
  // 그 외의 경우도 백엔드 URL 붙이기
  return `${API_BASE_URL}${imageUrl.startsWith('/') ? '' : '/'}${imageUrl}`;
};

export default function ProductManagement() {
  const [products, setProducts] = useState<Product[]>([]);
  const [stats, setStats] = useState<ProductStats>({ total: 0, selling: 0, soldout: 0, avg_price: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 검색/필터
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const limit = 12;

  // 모달 상태
  const [editModal, setEditModal] = useState(false);
  const [deleteModal, setDeleteModal] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [editForm, setEditForm] = useState({ name: '', price: 0, stock_quantity: 0, category: '', description: '' });
  const [actionLoading, setActionLoading] = useState(false);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error', message: string } | null>(null);

  const categories = ['전체 카테고리', 'Tops', 'Bottoms', 'Outerwear', 'Dresses', 'Accessories', 'Shoes'];

  // 상품 목록 조회
  const fetchProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { page, limit };
      if (search) params.search = search;
      if (category !== 'all' && category !== '전체 카테고리') params.category = category;

      const response = await client.get('/products', { params });
      setProducts(response.data.products || []);
      setStats(response.data.stats || { total: 0, selling: 0, soldout: 0, avg_price: 0 });
      setTotalPages(Math.ceil((response.data.total || 0) / limit));
    } catch (err: any) {
      setError(err.response?.data?.detail || '상품 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [page, category]);

  // 검색 실행
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProducts();
  };

  // 수정 모달 열기
  const openEditModal = (product: Product) => {
    setSelectedProduct(product);
    setEditForm({
      name: product.name,
      price: product.price,
      stock_quantity: product.stock_quantity,
      category: product.category,
      description: product.description || ''
    });
    setEditModal(true);
    setActionResult(null);
  };

  // 삭제 모달 열기
  const openDeleteModal = (product: Product) => {
    setSelectedProduct(product);
    setDeleteModal(true);
    setActionResult(null);
  };

  // 상품 수정
  const handleUpdate = async () => {
    if (!selectedProduct) return;
    setActionLoading(true);
    try {
      await client.patch(`/products/${selectedProduct.id}`, editForm);
      setActionResult({ type: 'success', message: '상품이 수정되었습니다.' });
      setTimeout(() => {
        setEditModal(false);
        fetchProducts();
      }, 1000);
    } catch (err: any) {
      setActionResult({ type: 'error', message: err.response?.data?.detail || '수정에 실패했습니다.' });
    } finally {
      setActionLoading(false);
    }
  };

  // 상품 삭제
  const handleDelete = async () => {
    if (!selectedProduct) return;
    setActionLoading(true);
    try {
      await client.delete(`/products/${selectedProduct.id}`);
      setActionResult({ type: 'success', message: '상품이 삭제되었습니다.' });
      setTimeout(() => {
        setDeleteModal(false);
        fetchProducts();
      }, 1000);
    } catch (err: any) {
      setActionResult({ type: 'error', message: err.response?.data?.detail || '삭제에 실패했습니다.' });
    } finally {
      setActionLoading(false);
    }
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
            <Package className="text-purple-500" /> 상품 관리
          </h1>
          <p className="text-gray-500 mt-1">등록된 상품 조회, 수정 및 삭제</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchProducts} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> 새로고침
          </Button>
          <Link to="/admin/upload">
            <Button className="flex items-center gap-2">
              <Plus size={16} /> 상품 등록
            </Button>
          </Link>
        </div>
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">전체 상품</p>
          <p className="text-2xl font-bold">{stats.total}</p>
        </div>
        <div className="bg-gradient-to-br from-green-500 to-green-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">판매중</p>
          <p className="text-2xl font-bold">{stats.selling}</p>
        </div>
        <div className="bg-gradient-to-br from-orange-500 to-orange-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">품절</p>
          <p className="text-2xl font-bold">{stats.soldout}</p>
        </div>
        <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-4 rounded-2xl">
          <p className="text-sm opacity-80">평균 가격</p>
          <p className="text-2xl font-bold">₩{stats.avg_price.toLocaleString()}</p>
        </div>
      </div>

      {/* 검색/필터 */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl border p-4 mb-6">
        <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
            <input
              type="text"
              placeholder="상품명으로 검색..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter size={18} className="text-gray-400" />
            <select
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
              className="px-4 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
            >
              {categories.map(cat => (
                <option key={cat} value={cat === '전체 카테고리' ? 'all' : cat}>{cat}</option>
              ))}
            </select>
          </div>
          <Button type="submit">검색</Button>
        </form>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* 상품 그리드 */}
      {loading ? (
        <div className="flex justify-center items-center py-20">
          <Loader2 className="animate-spin text-purple-500" size={40} />
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <Package size={60} className="mx-auto mb-4 opacity-30" />
          <p>등록된 상품이 없습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {products.map(product => (
            <div key={product.id} className="bg-white dark:bg-gray-800 rounded-2xl border overflow-hidden group hover:shadow-lg transition-shadow">
              <div className="relative aspect-square bg-gray-100">
                {/* ✅ FIX: getImageUrl 함수로 이미지 URL 변환 */}
                <img
                  src={getImageUrl(product.image_url)}
                  alt={product.name}
                  className="w-full h-full object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).src = 'https://placehold.co/400x400?text=No+Image'; }}
                />
                {/* 호버 액션 */}
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <Link to={`/products/${product.id}`}>
                    <button className="p-2 bg-white rounded-full hover:bg-gray-100">
                      <Eye size={18} />
                    </button>
                  </Link>
                  <button onClick={() => openEditModal(product)} className="p-2 bg-white rounded-full hover:bg-gray-100">
                    <Edit2 size={18} />
                  </button>
                  <button onClick={() => openDeleteModal(product)} className="p-2 bg-white rounded-full hover:bg-red-100 text-red-500">
                    <Trash2 size={18} />
                  </button>
                </div>
                {/* 품절 뱃지 */}
                {product.stock_quantity === 0 && (
                  <div className="absolute top-2 left-2 bg-red-500 text-white text-xs px-2 py-1 rounded-full">품절</div>
                )}
              </div>
              <div className="p-4">
                <p className="text-xs text-purple-500 mb-1">{product.category}</p>
                <h3 className="font-medium text-sm truncate">{product.name}</h3>
                <p className="text-lg font-bold mt-1">₩{product.price.toLocaleString()}</p>
                <p className="text-xs text-gray-500 mt-1">재고: {product.stock_quantity}개</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-8">
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage(p => p - 1)}
          >
            이전
          </Button>
          <span className="px-4 text-gray-600">{page} / {totalPages}</span>
          <Button
            variant="outline"
            disabled={page === totalPages}
            onClick={() => setPage(p => p + 1)}
          >
            다음
          </Button>
        </div>
      )}

      {/* 수정 모달 */}
      {editModal && selectedProduct && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">상품 수정</h2>
              <button onClick={() => setEditModal(false)}><X size={24} /></button>
            </div>

            {actionResult && (
              <div className={`p-3 rounded-lg mb-4 flex items-center gap-2 ${actionResult.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                {actionResult.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
                {actionResult.message}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">상품명</label>
                <input
                  type="text"
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">가격</label>
                  <input
                    type="number"
                    value={editForm.price}
                    onChange={(e) => setEditForm({ ...editForm, price: parseInt(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">재고</label>
                  <input
                    type="number"
                    value={editForm.stock_quantity}
                    onChange={(e) => setEditForm({ ...editForm, stock_quantity: parseInt(e.target.value) || 0 })}
                    className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">카테고리</label>
                <select
                  value={editForm.category}
                  onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                >
                  {categories.filter(c => c !== '전체 카테고리').map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">설명</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-6">
              <Button variant="outline" className="flex-1" onClick={() => setEditModal(false)}>취소</Button>
              <Button className="flex-1" onClick={handleUpdate} disabled={actionLoading}>
                {actionLoading ? <Loader2 className="animate-spin" size={18} /> : '저장'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {deleteModal && selectedProduct && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl w-full max-w-sm p-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Trash2 className="text-red-500" size={32} />
              </div>
              <h2 className="text-xl font-bold mb-2">상품 삭제</h2>
              <p className="text-gray-500 mb-2">"{selectedProduct.name}"을(를) 삭제하시겠습니까?</p>
              <p className="text-xs text-red-500 mb-4">⚠️ 이미지와 모든 데이터가 완전히 삭제됩니다.</p>

              {actionResult && (
                <div className={`p-3 rounded-lg mb-4 flex items-center justify-center gap-2 ${actionResult.type === 'success' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                  {actionResult.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
                  {actionResult.message}
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1" onClick={() => setDeleteModal(false)}>취소</Button>
                <Button variant="destructive" className="flex-1" onClick={handleDelete} disabled={actionLoading}>
                  {actionLoading ? <Loader2 className="animate-spin" size={18} /> : '삭제'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}