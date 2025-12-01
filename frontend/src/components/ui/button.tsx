import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { twMerge } from 'tailwind-merge'; 

// 버튼 변형 타입 정의
export type ButtonVariant = 'default' | 'secondary' | 'outline' | 'ghost' | 'link';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  isLoading?: boolean;
}

// 버튼 스타일 정의 함수
const getButtonClasses = (variant: ButtonVariant) => {
  switch (variant) {
    case 'default':
      return 'bg-purple-600 text-white hover:bg-purple-700 shadow-md';
    case 'secondary':
      return 'bg-gray-200 text-gray-800 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600 shadow-sm';
    case 'outline':
      return 'border border-purple-500 text-purple-600 hover:bg-purple-50 dark:border-purple-400 dark:text-purple-400';
    case 'ghost':
      return 'hover:bg-gray-100 dark:hover:bg-gray-800';
    case 'link':
      return 'text-purple-600 dark:text-purple-400 underline-offset-4 hover:underline';
    default:
      return 'bg-purple-600 text-white hover:bg-purple-700 shadow-md';
  }
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', isLoading, children, disabled, ...props }, ref) => {
    
    // 로딩 인디케이터
    const loadingSpinner = (
      <svg className="animate-spin h-5 w-5 mr-3" viewBox="0 0 24 24">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
        <path className="opacity-75 fill-none stroke-white" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
    );

    return (
      <button
        className={twMerge(
          'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500',
          getButtonClasses(variant),
          (isLoading || disabled) && 'opacity-60 cursor-not-allowed',
          className
        )}
        ref={ref}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading ? loadingSpinner : null}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';

export { Button };