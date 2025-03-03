import asyncio
from typing import Dict, Optional
import logging
from pydantic import BaseModel, Field
from datetime import datetime

from api.exchange_base import BaseExchange
from core.order_manager import OrderManager
from core.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class TradeSignal(BaseModel):
    symbol: str
    action: str  # 'buy'/'sell'
    quantity: float
    strategy_id: str
    timestamp: datetime = Field(default_factory=datetime.now)


class OrderStatus(BaseModel):
    order_id: str
    status: str  # 'filled'/'partial'/'canceled'/'rejected'
    filled_quantity: float
    avg_price: float
    timestamp: datetime


class StrategyExecutor:
    """策略执行核心模块"""

    def __init__(
        self,
        exchange: BaseExchange,
        order_manager: OrderManager,
        risk_manager: RiskManager,
        config: dict
    ):
        self.exchange = exchange
        self.order_mgr = order_manager
        self.risk_mgr = risk_manager
        self.config = config

        # 异步事件循环
        self.loop = asyncio.get_event_loop()
        self.active_orders: Dict[str, asyncio.Task] = {}
        self.signal_queue = asyncio.Queue()

        # 初始化执行器
        self._setup_logging()

    def _setup_logging(self):
        """配置执行日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def process_signal(self, signal: TradeSignal):
        """异步处理交易信号"""
        try:
            # 风控检查
            if not self.risk_mgr.check_order_risk(signal):
                raise ValueError("风控规则拒绝该交易信号")

            # 生成订单
            order = self.order_mgr.create_order(
                symbol=signal.symbol,
                action=signal.action,
                quantity=signal.quantity,
                strategy_id=signal.strategy_id
            )

            # 提交订单
            task = self.loop.create_task(
                self._submit_order(order)
            )
            self.active_orders[order.order_id] = task

            logger.info(f"成功提交订单 {order.order_id}")

        except Exception as e:
            logger.error(f"信号执行失败: {str(e)}", exc_info=True)
            self.order_mgr.update_order_status(
                order.order_id,
                'failed',
                error=str(e)
            )

    async def _submit_order(self, order):
        """异步执行订单提交"""
        try:
            # 调用交易所API
            result = await self.exchange.place_order(
                symbol=order.symbol,
                side=order.action,
                quantity=order.quantity,
                order_type='limit' if self.config['use_limit_order'] else 'market'
            )

            # 更新订单状态
            self.order_mgr.update_order_status(
                order.order_id,
                result['status'],
                filled_quantity=result['filled'],
                avg_price=result['price']
            )

            # 订单状态监听
            asyncio.create_task(
                self._monitor_order_status(order.order_id)
            )

        except Exception as e:
            logger.error(f"订单 {order.order_id} 执行异常: {str(e)}")

    async def _monitor_order_status(self, order_id: str):
        """订单状态持续监控"""
        while True:
            status = await self.exchange.get_order_status(order_id)
            self.order_mgr.update_order_status(
                order_id,
                status['state'],
                filled_quantity=status['filled'],
                avg_price=status['avg_price']
            )

            if status['state'] in ('filled', 'canceled', 'rejected'):
                del self.active_orders[order_id]
                break

            await asyncio.sleep(self.config['order_check_interval'])

    def stop(self):
        """停止执行器"""
        for task in self.active_orders.values():
            task.cancel()
        logger.info("策略执行器已安全停止")


# 单元测试
if __name__ == "__main__":
    class MockExchange(BaseExchange):
        async def place_order(self, *args, **kwargs):
            return {'status': 'filled', 'filled': 100, 'price': 50.0}

    executor = StrategyExecutor(
        exchange=MockExchange(),
        order_manager=OrderManager(),
        risk_manager=RiskManager(),
        config={'use_limit_order': False, 'order_check_interval': 5}
    )

    test_signal = TradeSignal(
        symbol="BTC/USDT",
        action="buy",
        quantity=0.1,
        strategy_id="ma_crossover_001"
    )

    asyncio.run(executor.process_signal(test_signal))