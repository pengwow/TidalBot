import heapq
import pandas as pd
from datetime import datetime
from typing import Callable, Dict, List, Optional, Union
from collections import defaultdict
from strategies.base_strategy import BaseStrategy
from strategies.moving_average import MovingAverageStrategy

# 事件类型定义（用于优先队列排序）
EVENT_TYPES = {
    'MARKET': 0,  # 市场数据事件（价格更新）
    'SIGNAL': 1,  # 信号事件（买入/卖出）
    'ORDER': 2,  # 订单事件（执行交易）
    'LOG': 3  # 日志事件（用于调试）
}


class Event:
    """事件基类"""

    def __init__(self, event_type: str, timestamp: datetime, data: dict):
        self.type = event_type
        self.timestamp = timestamp
        self.data = data or {}

    def __lt__(self, other: 'Event') -> bool:
        # 优先队列排序：时间早的事件优先；同一时间按事件类型优先级（MARKET > SIGNAL > ORDER > LOG）
        return (self.timestamp, EVENT_TYPES[self.type]) < (other.timestamp, EVENT_TYPES[other.type])


class MarketDataEvent(Event):
    """市场数据事件（价格更新）"""

    def __init__(self, symbol: str, price: float, timestamp: datetime):
        super().__init__('MARKET', timestamp, {'symbol': symbol, 'price': price})


class SignalEvent(Event):
    """信号事件（由策略生成）"""

    def __init__(self, symbol: str, signal: int, timestamp: datetime):
        super().__init__('SIGNAL', timestamp, {'symbol': symbol, 'signal': signal})


class OrderEvent(Event):
    """订单事件（执行交易）"""

    def __init__(self, symbol: str, order_type: str, quantity: float, side: str,
                 timestamp: datetime):
        super().__init__('ORDER', timestamp, {
            'symbol': symbol,
            'order_type': order_type,  # 'market' 或 'limit'
            'quantity': quantity,
            'side': side,  # 'buy' 或 'sell'
        })

    def execute(self, market_price: float) -> None:
        """模拟订单执行（以市价成交为例）"""
        if self.order_type != 'market':
            raise NotImplementedError("仅支持市价单回测")

        # 创建交易记录
        trade_price = market_price
        quantity = self.quantity
        self.data['filled_quantity'] = quantity
        self.data['trade_price'] = trade_price


class Backtester:
    """回测引擎（事件驱动）"""

    def __init__(self):
        self.event_queue = []  # 优先队列（堆）
        self.handlers = defaultdict(Callable)  # 事件处理器映射
        self.portfolio = {'cash': 100000.0, 'positions': defaultdict(float)}  # 初始资金10万美元
        self.trades = []  # 交易记录列表
        self.last_time = None

    def add_event(self, event: Event) -> None:
        heapq.heappush(self.event_queue, event)

    def bind_handler(self, event_type: str, handler: Callable) -> None:
        self.handlers[event_type] = handler

    def run(self) -> None:
        """运行回测"""
        while self.event_queue:
            event = heapq.heappop(self.event_queue)

            # 更新最后处理时间
            self.last_time = event.timestamp

            # 分发事件到处理器
            if event.type in self.handlers:
                self.handlers[event.type](event)
            else:
                print(f"No handler for event type: {event.type}", file=sys.stderr)

    def on_market_data(self, event: MarketDataEvent) -> None:
        """处理市场数据事件（触发信号生成）"""
        # 示例：当收到市场数据时，调用策略生成信号
        # 需在初始化时绑定具体策略的信号生成逻辑
        pass

    def on_signal(self, event: SignalEvent) -> None:
        """处理信号事件（生成订单）"""
        symbol = event.data['symbol']
        signal = event.data['signal']

        if signal == 1:
            # 买入信号：以市价下单
            order = OrderEvent(
                symbol=symbol,
                order_type='market',
                quantity=100,  # 示例：固定交易量
                side='buy',
                timestamp=event.timestamp
            )
            self.add_event(order)
        elif signal == -1:
            # 卖出信号：卖出当前持仓
            position = self.portfolio['positions'][symbol]
            if position > 0:
                order = OrderEvent(
                    symbol=symbol,
                    order_type='market',
                    quantity=position,
                    side='sell',
                    timestamp=event.timestamp
                )
                self.add_event(order)

    def on_order(self, event: OrderEvent) -> None:
        """处理订单事件（执行交易并更新持仓）"""
        # 模拟订单执行（需匹配当前市场数据）
        # 这里假设订单执行时的市场价格与MarketDataEvent一致
        market_price = None
        # 需要根据symbol查找最新的市场数据价格（需维护一个价格历史记录）
        # 此处简化为直接取event中的price（实际需从市场数据事件中获取最新价格）
        # 示例：假设通过某种方式获取到当前价格（如全局变量）
        # market_price = get_latest_price(symbol)
        # 以下为示例逻辑：
        if 'trade_price' not in event.data:
            raise ValueError("Order event缺少交易价格")
        trade_price = event.data['trade_price']

        # 更新资金和持仓
        quantity = event.data['filled_quantity']
        cost = trade_price * quantity
        side = event.data['side']

        if side == 'buy':
            self.portfolio['cash'] -= cost
            self.portfolio['positions'][symbol] += quantity
        else:
            self.portfolio['cash'] += cost
            self.portfolio['positions'][symbol] -= quantity

        # 记录交易
        self.trades.append({
            'timestamp': event.timestamp,
            'symbol': symbol,
            'side': side,
            'price': trade_price,
            'quantity': quantity,
            'cash_change': -cost if side == 'buy' else cost
        })

    def on_log(self, event: Event) -> None:
        """处理日志事件"""
        print(f"[{event.timestamp}] {event.data.get('message', '')}")


class BacktesterWithStrategy(Backtester):
    def __init__(self, strategy: BaseStrategy, data: pd.DataFrame):
        """集成策略的回测引擎"""
        super().__init__()
        self.strategy = strategy
        self.data = data

        # 绑定事件处理器
        self.bind_handler('MARKET', self.on_market_data)
        self.bind_handler('SIGNAL', self.on_signal)
        self.bind_handler('ORDER', self.on_order)
        self.bind_handler('LOG', self.on_log)

        # 注册策略的signal方法到事件队列
        self._schedule_signals()

    def _schedule_signals(self) -> None:
        """根据策略生成信号事件"""
        for i, row in self.data.iterrows():
            timestamp = datetime.fromtimestamp(row['timestamp'])
            price = row['close']

            # 创建市场数据事件
            market_event = MarketDataEvent(
                symbol='AAPL',  # 示例：假设交易标的为AAPL
                price=price,
                timestamp=timestamp
            )
            self.add_event(market_event)

            # 处理市场数据后生成信号
            signal = self.strategy.signal(row)
            if signal != 0:
                signal_event = SignalEvent(
                    symbol='AAPL',
                    signal=signal,
                    timestamp=timestamp
                )
                self.add_event(signal_event)

    def run(self) -> None:
        """运行回测（覆盖父类方法以确保正确初始化）"""
        super().run()

        # 输出回测结果
        self._calculate_performance()

    def _calculate_performance(self) -> None:
        """计算回测绩效指标"""
        total_return = (self.portfolio['cash'] - 100000.0) / 100000.0
        max_drawdown = 0.0
        peak = 100000.0

        for trade in self.trades:
            cash_change = trade['cash_change']
            current_cash = 100000.0 + sum(trade['cash_change'] for trade in self.trades if self.trades.index(trade) <= self.trades.index(trade))
            # ... 实际需按时间顺序累加现金变化计算最大回撤

        print(f"总收益率: {total_return:.2%}")
        print(f"最大回撤: {max_drawdown:.2%}")


if __name__ == '__main__':
    import pandas as pd

    # 1. 准备数据（需包含时间戳和价格）
    data = pd.DataFrame({
        'timestamp': [1712073575, 1712073576, 1712073577],  # Unix时间戳
        'close': [185.5, 186.0, 184.8]
    })

    # 2. 创建策略实例
    sma_config = {'short_window': 2, 'long_window': 5}
    strategy = MovingAverageStrategy(sma_config)

    # 3. 初始化回测引擎
    backtester = BacktesterWithStrategy(strategy, data)

    # 4. 运行回测
    backtester.run()

    # 5. 查看结果
    print(backtester.portfolio)
    print(backtester.trades)