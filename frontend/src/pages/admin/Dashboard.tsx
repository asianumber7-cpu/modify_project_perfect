import React, { useState } from 'react';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, ArcElement,
} from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';
import { TrendingUp, Users, Package, DollarSign, ListChecks, Loader2, Mail } from 'lucide-react'; 
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button'; 
import { useQuery } from '@tanstack/react-query';
import client from '@/api/client';
import EmailBroadcastModal from '../../components/common/modals/EmailBroadcastModal'; 

interface SalesData { label: string; value: number; }
interface DashboardStatsResponse {
    total_revenue: number; new_orders: number; visitors: number; growth_rate: number;
    weekly_sales_trend: SalesData[];
    category_sales_pie: SalesData[];
}

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, ArcElement);

const statConfig = [
    { key: 'total_revenue', title: '총 매출', icon: DollarSign, color: 'text-green-500', format: (v: number) => `₩${v.toLocaleString()}` },
    { key: 'new_orders', title: '신규 주문', icon: Package, color: 'text-purple-500', format: (v: number) => `${v}건` },
    { key: 'visitors', title: '방문자 수', icon: Users, color: 'text-blue-500', format: (v: number) => `${v.toLocaleString()}명` },
    { key: 'growth_rate', title: '성장률', icon: TrendingUp, color: 'text-red-500', format: (v: number) => `+${v}%` },
];

const useDashboardStats = (timeRange: 'daily' | 'weekly' | 'monthly') => {
    return useQuery<DashboardStatsResponse>({
        queryKey: ['adminDashboard', timeRange],
        queryFn: async () => {
            // 🚨 FIX: baseURL에 /api/v1이 포함되어 있으므로 경로에서 제거
            const res = await client.get(`/admin/dashboard`, {
                params: { time_range: timeRange }
            });
            return res.data;
        },
        staleTime: 60000,
        retry: 1,
    });
};

export default function Dashboard() {
    const [timeRange, setTimeRange] = useState<'daily' | 'weekly' | 'monthly'>('weekly');
    
    // 모달 상태 관리
    const [isEmailModalOpen, setIsEmailModalOpen] = useState(false);

    const { data: stats, isLoading, isError } = useDashboardStats(timeRange);

    if (isLoading) {
        return <div className="p-10 text-center text-xl dark:text-gray-300 flex items-center justify-center min-h-[50vh]"><Loader2 className="animate-spin mr-3" /> 데이터 로딩 중...</div>;
    }

    if (isError || !stats) {
        return <div className="p-10 text-center text-red-500 text-xl">통계 데이터를 불러올 수 없습니다. 관리자 권한을 확인해주세요.</div>;
    }
    
    const lineData = {
        labels: stats.weekly_sales_trend.map(d => d.label),
        datasets: [{
            label: `${timeRange} 매출 (만원)`,
            data: stats.weekly_sales_trend.map(d => d.value),
            borderColor: 'rgb(99, 102, 241)',
            backgroundColor: 'rgba(99, 102, 241, 0.5)',
            tension: 0.4,
        }],
    };
    
    const chartColors = ['rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)', 'rgba(255, 206, 86, 0.8)', 'rgba(75, 192, 192, 0.8)'];

    const doughnutData = {
        labels: stats.category_sales_pie.map(d => d.label),
        datasets: [{
            data: stats.category_sales_pie.map(d => d.value),
            backgroundColor: stats.category_sales_pie.map((d, i) => chartColors[i % chartColors.length]),
            borderWidth: 0,
        }],
    };

    return (
        <div className="p-6 space-y-6 bg-gray-50 dark:bg-gray-900 min-h-screen">
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-3xl font-bold text-gray-800 dark:text-white">Admin Dashboard</h1>
                
                <div className="flex items-center space-x-4">
                    {/* 단체 메일 발송 버튼 */}
                    <Button 
                        variant="outline" 
                        className="flex items-center bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                        onClick={() => setIsEmailModalOpen(true)}
                    >
                        <Mail size={20} className="mr-2" /> 
                        단체 메일
                    </Button>

                    {/* 상품 업로드 링크 */}
                    <Link to="/admin/upload">
                        <Button variant="default" className="flex items-center">
                            <ListChecks size={20} className="mr-2" /> 상품 관리/업로드
                        </Button>
                    </Link>
                </div>
            </div>

            <div className="mb-8 flex space-x-2">
                <Button 
                    variant={timeRange === 'daily' ? 'default' : 'secondary'} 
                    onClick={() => setTimeRange('daily')}
                    disabled={isLoading}
                >일간</Button>
                <Button 
                    variant={timeRange === 'weekly' ? 'default' : 'secondary'} 
                    onClick={() => setTimeRange('weekly')}
                    disabled={isLoading}
                >주간</Button>
                <Button 
                    variant={timeRange === 'monthly' ? 'default' : 'secondary'} 
                    onClick={() => setTimeRange('monthly')}
                    disabled={isLoading}
                >월간</Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {statConfig.map((stat, index) => {
                    const value = stat.format((stats as any)[stat.key]);
                    return (
                        <div key={index} className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-500 dark:text-gray-400">{stat.title}</p>
                                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mt-1">{value}</h3>
                            </div>
                            <div className={`p-3 rounded-full bg-gray-50 dark:bg-gray-700 ${stat.color}`}>
                                <stat.icon size={24} />
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700">
                    <h3 className="font-bold text-lg mb-4 text-gray-800 dark:text-white">
                        {timeRange.charAt(0).toUpperCase() + timeRange.slice(1)} 매출 추이
                    </h3>
                    <Line options={{ responsive: true, plugins: { legend: { position: 'top' as const } } }} data={lineData} />
                </div>

                <div className="bg-white dark:bg-gray-800 p-6 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700">
                    <h3 className="font-bold text-lg mb-4 text-gray-800 dark:text-white">카테고리별 판매</h3>
                    <div className="flex justify-center">
                        <div className="w-64">
                            <Doughnut data={doughnutData} />
                        </div>
                    </div>
                </div>
            </div>

            {/* 모달 컴포넌트 */}
            <EmailBroadcastModal 
                isOpen={isEmailModalOpen} 
                onClose={() => setIsEmailModalOpen(false)} 
            />
        </div>
    );
}