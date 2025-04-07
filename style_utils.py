import streamlit as st


def apply_custom_styles():
    st.markdown("""
        <style>
        /* 헤더 숨기기 */
        header {
            display: none !important;
        }
                
        /* 전체 페이지 배경 */
        .stApp {
            background: linear-gradient(135deg, #f0f2f6 0%, #e3e6e8 100%);
        }
        
        /* 메인 컨테이너 스타일링 */
        .main .block-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            padding: 2rem;
            max-width: 1400px;
            margin-top: 3rem;
            position: relative;
        }
                
        /* footer 숨기기 */
        footer {
            display: none !important;
        }
                
        /* 상단 장식 */
        .main .block-container:before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 10px;
            background: #E31837;
            border-radius: 20px 20px 0 0;
        }
        
        /* 로고 컨테이너 */
        .logo-container {
            text-align: center;
            padding: 1rem 0 2rem 0;
            border-bottom: 1px solid #eee;
            margin-bottom: 2rem;
        }
        
        .logo-image {
            max-width: 200px;
            margin-bottom: 1.5rem;
        }
        
        /* 헤더 텍스트 */
        .main-header {
            color: #E31837;
            font-size: 2.2rem;
            font-weight: bold;
            text-align: center;
            margin: 0.5rem 0;
        }
        
        .sub-header {
            color: #666;
            font-size: 1.3rem;
            text-align: center;
            margin-bottom: 1rem;
        }
        
        /* 입력 필드 스타일링 */
        .stTextInput > div > div > input {
            border-radius: 8px;
            padding: 0.8rem 1rem;
            border: 2px solid #eee;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #E31837;
            box-shadow: 0 0 0 2px rgba(227,24,55,0.2);
        }
        
        /* 기본 버튼 스타일링 (공통 스타일) */
        .stButton button {
            padding: 0.75rem 2rem !important;
            border-radius: 8px !important;
            border: none !important;
            width: 100% !important;
            font-size: 1.1rem !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }

        /* 모든 버튼 선택자를 더 포괄적으로 적용 */
        /* primary 버튼 (빨간색) */
        .stButton button[data-baseweb="button"][kind="primary"],
        .stButton button[data-baseweb="button"][type="primary"],
        .stButton button[type="primary"] {
            background-color: #E31837 !important;
            color: white !important;
        }

        /* secondary 버튼 */
        .stButton button[data-baseweb="button"][kind="secondary"],
        .stButton button[data-baseweb="button"][type="secondary"],
        .stButton button[type="secondary"],
        .stButton button[data-testid*="secondary"] {
            background-color: #3A5875 !important;
            color: white !important;
        }

        /* tertiary 버튼 */
        .stButton button[data-baseweb="button"][kind="tertiary"],
        .stButton button[data-baseweb="button"][type="tertiary"],
        .stButton button[type="tertiary"],
        .stButton button[data-testid*="tertiary"] {
            background-color: #607D8B !important;
            color: white !important;
        }
                
        /* 알림 메시지 스타일링 */
        .stAlert {
            border-radius: 8px;
            margin: 1rem 0;
        }
        </style>
    """, unsafe_allow_html=True)

def apply_mode_indicator_styles():
    st.markdown("""
    <style>
    .mode-indicator {
        padding: 5px 0;
        margin-bottom: 20px;
        text-align: center;
        border-radius: 8px;
        transition: background-color 0.5s ease;
        position: relative;
        overflow: hidden;
    }
    
    .default-mode {
        background-color: #3A5875;  /* F27059에서 3A5875로 변경 */
        color: white;
        box-shadow: 0 4px 6px rgba(58, 88, 117, 0.3); /* 그림자 색상도 일치하게 변경 */
    }
                
    .labeling-mode {
        background-color: #1ABC9C; 
        color: white;
        box-shadow: 0 4px 6px rgba(26, 188, 156, 0.3)
    }
                
    .review-mode {
        background-color: #FF9F1C; 
        color: white;
        box-shadow: 0 4px 6px rgba(255, 159, 28, 0.3);
    }
                
    .confirmed-mode {
        background-color: #3498DB; 
        color: white;
        box-shadow: 0 4px 6px rgba(255, 159, 28, 0.3);
    }
    
    .mode-title {
        font-size: 20px;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .mode-description {
        font-size: 14px;
        opacity: 0.9;
    }
    
    .flash-animation {
        animation: flash-bg 1s ease;
    }
    
    @keyframes flash-bg {
        0% { opacity: 0.5; }
        50% { opacity: 1; }
        100% { opacity: 0.8; }
    }
    
    .progress-bar {
        height: 4px;
        width: 100%;
        position: absolute;
        bottom: 0;
        left: 0;
        background: rgba(255, 255, 255, 0.3);
    }
    
    .progress-indicator {
        height: 100%;
        background-color: white;
        width: 0%;
        transition: width 0.5s ease;
    }
    </style>
    """, unsafe_allow_html=True)



def apply_buttons_styles():
    """홈 버튼과 새로고침 버튼을 위한 CSS 스타일 추가"""
    st.markdown("""
    <style>
    .button-container {
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    
    .custom-button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
        cursor: pointer;
        transition: all 0.3s ease;
        border: none;
        font-size: 22px;
    }
    
    .home-button {
        background-color: #FF4B4B;
        color: white;
    }
    
    .refresh-button {
        background-color: #1E88E5;
        color: white;
    }
    
    .custom-button:hover {
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
        transform: translateY(-2px);
    }
    
    .home-button:hover {
        background-color: #FF6B6B;
    }
    
    .refresh-button:hover {
        background-color: #42A5F5;
    }
    
    .start-button {
    background-color: #4CAF50;  /* 녹색 계열 */
    color: white;
    }

    .start-button:hover {
        background-color: #66BB6A;
    }
                
    .custom-button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }
    
    .button-tooltip {
        position: absolute;
        background-color: #333;
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        transition: opacity 0.3s ease;
        pointer-events: none;
        top: 50%;
        left: 110%;
        transform: translateY(-50%);
    }
    
    .button-wrapper:hover .button-tooltip {
        opacity: 1;
    }
    
    /* 애니메이션 효과 추가 */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .pulse-animation {
        animation: pulse 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)


def apply_navigation_styles():
    """네비게이션 UI 스타일을 적용하는 함수"""
    st.markdown("""
    <style>
    .image-nav-container {
        text-align: center;
        padding: 10px 0;
        margin-bottom: 15px;
    }
    .file-name-container {
        background-color: #f0f2f6;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }
    .file-name {
        font-size: 1.1em;
        font-weight: 500;
        color: #222;
        word-break: break-all;
    }
    .image-counter {
        font-weight: bold;
        color: #333;
        margin-bottom: 5px;
    }
    .progress-container {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        margin: 10px 0;
    }
    .progress-bar {
        background-color: #3366cc;
        height: 8px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_pagination_styles():
    """페이지네이션 UI 스타일을 적용하는 함수"""
    st.markdown("""
    <style>
    /* 전체 페이지네이션 컨테이너 */
    .pagination-container {
        text-align: center;
        padding: 15px 0;
        margin: 20px 0;
        background-color: #f8f9fa;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* 페이지 카운터 표시 */
    .page-counter {
        font-weight: bold;
        color: #333;
        margin-bottom: 10px;
        font-size: 1.1em;
    }
    
    /* 진행 표시줄 */
    .progress-container {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        margin: 10px 0 15px 0;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    
    .progress-bar {
        background-color: #3366cc;
        height: 8px;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    </style>
    """, unsafe_allow_html=True)

def apply_navigation_styles():
    """네비게이션 UI 스타일을 적용하는 함수"""
    st.markdown("""
    <style>
    .image-nav-container {
        text-align: center;
        padding: 10px 0;
        margin-bottom: 15px;
    }
    .file-name-container {
        background-color: #f0f2f6;
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }
    .file-name {
        font-size: 1.1em;
        font-weight: 500;
        color: #222;
        word-break: break-all;
    }
    .image-counter {
        font-weight: bold;
        color: #333;
        margin-bottom: 5px;
    }
    .progress-container {
        width: 100%;
        background-color: #e0e0e0;
        border-radius: 10px;
        height: 8px;
        margin: 10px 0;
    }
    .progress-bar {
        background-color: #3366cc;
        height: 8px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)


def apply_card_style():
    st.markdown("""
    <style>
    .metric-card {
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 34px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 16px;
        opacity: 0.9;
    }
    .metric-icon {
        font-size: 24px;
        margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
