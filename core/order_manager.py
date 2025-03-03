import asyncio
from typing import Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

class OrderType(str, Enum):
    LIMIT = 'limit'
    MARKET = 'market'
    STOP_LOSS = 'stop_loss'
    TAKE_PROFIT = 'take_profit'

class TradeType(str, Enum):
    SPOT = 'spot'
    PERPETUAL = 'perpetual'

class OrderStatus(str, Enum):
    NEW = 'new'
    PARTIALLY_FILLED = 'partially_filled'
    FILLED = 'filled'
    CANCELED = 'canceled'
    REJECTED = 'rejected'
    EXPIRED = 'expired'

class Order(BaseModel):
    order_id: str
    symbol: str
    order_type: OrderType
    trade_type: TradeType
    side: str  # buy/sell
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None  # 用于止损止盈单
    leverage: int = 1  # 永续合约杠杆
    margin: Optional[float] = None  # 保证金金额
    status: OrderStatus = OrderStatus.NEW
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    filled_quantity: float = 0.0
    avg_price: float = 0.0

class OrderManager:
    MIN_MAINTENANCE_MARGIN = 0.05  # 5%维持保证金率

    def __init__(self):
        self.active_orders: Dict[str, Order] = {}
        self.order_history: Dict[str, Order] = {}
        self._lock = asyncio.Lock()

    async def create_order(self, order: Order, risk_manager) -> Order:
        async with self._lock:
            # 风险预检查
            if not risk_manager.check_order_risk(order):
                order.status = OrderStatus.REJECTED
                order.updated_at = datetime.now()
                self.order_history[order.order_id] = order
                return order

            # 永续合约保证金计算
            if order.trade_type == TradeType.PERPETUAL:
                required_margin = self.calculate_required_margin(order)
                position = self.positions.get(order.symbol, {})

                # 保证金充足性检查
                if position.get('margin', 0) < required_margin * 1.1:  # 保留10%缓冲
                    order.status = OrderStatus.REJECTED
                    order.updated_at = datetime.now()
                    self.order_history[order.order_id] = order
                    return order

            self.active_orders[order.order_id] = order
            self.order_history[order.order_id] = order
            return order

    async def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: float = 0.0,
        avg_price: float = 0.0
    ) -> Optional[Order]:
        async with self._lock:
            if order_id in self.active_orders:
                order = self.active_orders[order_id]
                order.status = status
                order.filled_quantity = filled_quantity
                order.avg_price = avg_price
                order.updated_at = datetime.now()

                if status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
                    self.active_orders.pop(order_id)

                return order
            return None

    async def cancel_order(self, order_id: str) -> bool:
        async with self._lock:
            if order_id in self.active_orders:
                order = self.active_orders.pop(order_id)
                order.status = OrderStatus.CANCELED
                return True
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        return self.active_orders.get(order_id) or self.order_history.get(order_id)

    async def sync_positions(self, exchange):
        """同步交易所仓位信息"""
        positions = await exchange.get_positions()
        # 更新永续合约仓位和保证金
        for p in positions:
            if p['type'] == TradeType.PERPETUAL:
                self.positions[p['symbol']] = {
                    'quantity': p['positionAmt'],
                    'entry_price': p['entryPrice'],
                    'leverage': p['leverage'],
                    'margin': p['isolatedMargin']
                }
        # 现货仓位同步逻辑
        spot_balances = await exchange.get_spot_balances()
        for currency, balance in spot_balances.items():
            self.spot_balances[currency] = balance

    async def auto_cancel_orders(self, exchange):
        """自动撤单逻辑"""
        orders_to_cancel = [
            order_id for order_id, order in self.active_orders.items()
            if self._should_auto_cancel(order)
        ]
        for order_id in orders_to_cancel:
            await exchange.cancel_order(order_id)
            await self.cancel_order(order_id)

    def _should_auto_cancel(self, order: Order) -> bool:
        """判断是否需要自动撤单"""
        # 基于时间的撤单（30秒未成交）
        if (datetime.now() - order.created_at).total_seconds() > 30:
            return True

        # 永续合约强平检查
        if order.trade_type == TradeType.PERPETUAL:
            position = self.positions.get(order.symbol)
            if position and position['margin'] < self.MIN_MAINTENANCE_MARGIN:
                return True

        # 止损止盈触发检查
        if order.order_type in (OrderType.STOP_LOSS, OrderType.TAKE_PROFIT):
            mark_price = self.get_mark_price(order.symbol)
            if order.side == 'buy' and mark_price <= order.stop_price:
                return True
            elif order.side == 'sell' and mark_price >= order.stop_price:
                return True

        return False

    def calculate_required_margin(self, order: Order) -> float:
        """计算永续合约订单所需保证金"""
        if order.trade_type == TradeType.PERPETUAL:
            return (order.quantity * order.price) / order.leverage
        return 0.0