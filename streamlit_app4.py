import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import pyupbit

def get_connection():
    return sqlite3.connect('crypto_trades.db')

def load_data(coin_type=None):
    conn = get_connection()
    query = "SELECT * FROM trades"
    if coin_type:
        query += f" WHERE coin_type = '{coin_type}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def calculate_coin_performance(df, coin_type):
    if df.empty:
        return 0, 0, 0
    
    latest = df.iloc[-1]
    balance = latest[f'{coin_type.lower()}_balance']
    price = latest[f'{coin_type.lower()}_krw_price']
    krw_balance = latest['krw_balance']
    
    return balance, price, krw_balance

def main():
    st.title('Crypto Trading Dashboard')
    
    # 코인별 데이터 로드
    btc_df = load_data('BTC')
    eth_df = load_data('ETH')
    
    # 코인 선택
    selected_coin = st.selectbox('Select Coin', ['Both', 'BTC', 'ETH'])
    
    if selected_coin == 'Both':
        df = pd.concat([btc_df, eth_df]).reset_index(drop=True)
        # Sort by timestamp for combined view
        df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
        # Sort by timestamp for combined view
        df = df.sort_values('timestamp', ascending=False).reset_index(drop=True)
    elif selected_coin == 'BTC':
        df = btc_df
    else:
        df = eth_df
    
    if df.empty:
        st.warning('No trade data available.')
        return

    # 코인별 7일 거래 성공률과 현재 잔고
    st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] > div:first-child h3 {
            white-space: nowrap;
        }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) h3 {
            white-space: nowrap;
        }
        </style>
        """, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    def calculate_success_rate(df):
        if df.empty:
            return 0, 0
        sell_trades = df[df['decision'] == 'sell']
        if len(sell_trades) == 0:
            return 0, 0
        successful_trades = sell_trades.apply(
            lambda x: (x['eth_krw_price'] * (1 - 0.0005) - x['eth_avg_buy_price']) / x['eth_avg_buy_price'] > 0 
            if x['coin_type'] == 'ETH' else 
            (x['btc_krw_price'] * (1 - 0.0005) - x['btc_avg_buy_price']) / x['btc_avg_buy_price'] > 0, 
            axis=1
        ).sum()
        return successful_trades, len(sell_trades)
    
    with col1:
        st.subheader('Bitcoin 7-Day Performance')
        btc_success, btc_total = calculate_success_rate(btc_df)
        success_rate = (btc_success / btc_total * 100) if btc_total > 0 else 0
        btc_balance, btc_price, _ = calculate_coin_performance(btc_df, 'BTC')
        
        st.metric("Success Rate", f"{success_rate:.1f}%")
        st.metric("Total/Success Trades", f"{btc_total}/{btc_success}")
        
        # BTC 자산가치 계산
        btc_value = btc_balance * btc_price
        
    with col2:
        st.subheader('Ethereum 7-Day Performance')
        eth_success, eth_total = calculate_success_rate(eth_df)
        success_rate = (eth_success / eth_total * 100) if eth_total > 0 else 0
        eth_balance, eth_price, krw_balance = calculate_coin_performance(eth_df, 'ETH')
        
        st.metric("Success Rate", f"{success_rate:.1f}%")
        st.metric("Total/Success Trades", f"{eth_total}/{eth_success}")
        
        # ETH 자산가치 계산
        eth_value = eth_balance * eth_price
        
    # 총 자산가치 계산
    total_value = btc_value + eth_value + krw_balance
    
    # 자산 분배 시각화
    st.subheader('Portfolio Distribution')
    portfolio_data = {
        'Asset': ['BTC', 'ETH', 'KRW'],
        'Value': [btc_value, eth_value, krw_balance],
        'Percentage': [
            f"{(btc_value/total_value*100):.1f}%" if total_value > 0 else "0%",
            f"{(eth_value/total_value*100):.1f}%" if total_value > 0 else "0%",
            f"{(krw_balance/total_value*100):.1f}%" if total_value > 0 else "0%"
        ],
        'Balance': [
            f"{btc_balance:.8f}",
            f"{eth_balance:.8f}",
            f"₩{krw_balance:,.0f}"
        ]
    }
    
    col3, col4 = st.columns([2, 3])
    with col3:
        # 도넛 차트
        fig = px.pie(
            portfolio_data, 
            values='Value', 
            names='Asset',
            hole=0.6,
            title='Asset Distribution'
        )
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        
    with col4:
        # 상세 정보 테이블
        df_portfolio = pd.DataFrame(portfolio_data)
        st.dataframe(
            df_portfolio[['Asset', 'Balance', 'Percentage']],
            hide_index=True,
            use_container_width=True
        )

    # 거래 내역 분석
    st.header('Trading Analysis')
    
    # 거래 결정 분포
    st.subheader('Trade Decisions Distribution')
    decision_counts = df['decision'].value_counts()
    fig = px.pie(values=decision_counts.values, 
                 names=decision_counts.index, 
                 title=f'Trade Decisions ({selected_coin})')
    st.plotly_chart(fig)
    
    # Recent Trades 테이블 CSS
    st.markdown("""
        <style>
            .recent-trades-container {
                height: 400px;
                overflow-y: auto;
            }
            .stDataFrame {
                height: 400px;
            }
            .stDataFrame [data-testid="stDataFrameResizable"] {
                max-height: 400px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # 코인별 거래 내역
    st.subheader('Recent Trades')
    display_cols = ['timestamp', 'coin_type', 'decision', 'percentage', 'reason']
    st.dataframe(
        df[display_cols],
        height=400,
        hide_index=True
    )
    
    # 코인별 잔고 변화
    if selected_coin != 'Both':
        balance_col = f'{selected_coin.lower()}_balance'
        price_col = f'{selected_coin.lower()}_krw_price'
        
        st.subheader(f'{selected_coin} Balance History')
        fig = px.line(df, x='timestamp', y=balance_col, 
                     title=f'{selected_coin} Balance')
        st.plotly_chart(fig)
        
        st.subheader(f'{selected_coin} Price History')
        fig = px.line(df, x='timestamp', y=price_col,
                     title=f'{selected_coin} Price')
        st.plotly_chart(fig)
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader('BTC Balance History')
            fig = px.line(btc_df, x='timestamp', y='btc_balance')
            st.plotly_chart(fig)
        
        with col2:
            st.subheader('ETH Balance History')
            fig = px.line(eth_df, x='timestamp', y='eth_balance')
            st.plotly_chart(fig)

    # Trading Reflections 히스토리
    st.header('Trading History')
    st.markdown("### Recent Trading Reflections")

    # Reflection 데이터 준비 
    reflections_df = df[['timestamp', 'coin_type', 'reflection', 'reason', 'decision', 'percentage']].copy()
    reflections_df = reflections_df[reflections_df['reflection'].notna()]
    reflections_df['timestamp'] = pd.to_datetime(reflections_df['timestamp'])
    reflections_df = reflections_df.sort_values('timestamp', ascending=False)

    # radio 버튼 컨테이너 스크롤을 위한 CSS
    st.markdown("""
        <style>
            div[data-testid="stVerticalBlock"] > div:has(div.st-ae) {
                max-height: 200px !important;
                overflow-y: auto !important;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
            }
            
            .st-ae {
                border-bottom: 1px solid #eee;
                padding: 5px 0;
            }
            .st-ae:last-child {
                border-bottom: none;
            }
        </style>
    """, unsafe_allow_html=True)

    # 각 리플렉션을 radio 버튼으로 표시
    titles = [f"{row['timestamp'].strftime('%Y-%m-%d %H:%M')} - {row['coin_type']} ({row['decision'].upper()} {row['percentage']}%)" 
             for _, row in reflections_df.iterrows()]
    
    selected = st.radio("Select reflection to view details", 
                      titles,
                      label_visibility="collapsed")
    
    # 선택된 리플렉션의 세부 정보 표시
    if selected:
        idx = titles.index(selected)
        row = reflections_df.iloc[idx]
        
        st.markdown("---")
        st.markdown(f"**Details for {selected}**")
        st.markdown("**Reflection:**")
        st.write(row['reflection'])
        st.markdown("**Reason:**")
        st.write(row['reason'])

if __name__ == "__main__":
    main()