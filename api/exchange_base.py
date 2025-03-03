import abc
import logging
import requests
from typing import List, Dict, Any, Optional


class ExchangeBase(abc.ABC):
    """交易所基类，所有具体交易所适配器必须继承此类"""

    @abc.abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """初始化交易所实例
        :param config: 包含交易所参数的字典（如API密钥、端点）
        """
        self.config = config
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    def _normalize_quantity(self, quantity: float, symbol_info: Dict[str, Any]) -> float:
        """将数量转换为交易所最小单位
        :param quantity: 用户输入的数量（如1 BTC）
        :param symbol_info: 合约信息（包含 `min_quantity`）
        :return: 转换为最小单位的整数（如聪）
        """
        min_step = symbol_info["min_quantity"]
        return round(quantity * (1 / min_step))  # 根据精度调整

    def _denormalize_quantity(self, quantity: int, symbol_info: Dict[str, Any]) -> float:
        """将最小单位转换为可读数量
        :param quantity: 最小单位整数
        :param symbol_info: 合约信息
        :return: 格式化后的数量（如0.001 BTC）
        """
        step_size = symbol_info["step_size"]
        return quantity * step_size

    @abc.abstractmethod
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """获取交易对信息（如最小交易量、合约精度）
        :param symbol: 交易对（如 BTCUSDT）
        :return: 包含最小变动单位和合约大小的字典
        """
        pass

    @abc.abstractmethod
    def get_ticker_price(self, symbol: str) -> float:
        """获取最新价格
        :param symbol: 交易对
        :return: 当前价格（浮点数）
        """
        pass

    @abc.abstractmethod
    def place_order(
            self,
            symbol: str,
            side: str,  # "buy" 或 "sell"
            type: str,  # "limit", "market"
            quantity: float,
            price: Optional[float] = None
    ) -> str:
        """下单（返回订单ID）
        :param symbol: 交易对
        :param side: 买卖方向
        :param type: 订单类型
        :param quantity: 数量
        :param price: 限价价格（仅限限价单）
        :return: 订单ID
        """
        pass

    @abc.abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """撤单
        :param symbol: 交易对
        :param order_id: 订单ID
        :return: 撤单是否成功
        """
        pass

    @abc.abstractmethod
    def get_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """获取未平仓订单
        :param symbol: 交易对
        :return: 订单列表
        """
        pass

    @abc.abstractmethod
    def get_balance(self) -> Dict[str, float]:
        """获取账户余额（包括USDT、BTC等资产）
        :return: 资产字典
        """
        pass

    @abc.abstractmethod
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取持仓信息
        :param symbol: 交易对
        :return: 持仓详情（如数量、平均成本价）
        """
        pass

    @abc.abstractmethod
    def deposit(self, asset: str, amount: float) -> bool:
        """存入资产（如USDT充值）
        :param asset: 资产类型
        :param amount: 数量
        :return: 充值是否成功
        """
        pass

    @abc.abstractmethod
    def withdraw(self, asset: str, amount: float) -> bool:
        """提现资产
        :param asset: 资产类型
        :param amount: 数量
        :return: 提现是否成功
        """
        pass

    # 可扩展的公共方法
    def _request(
            self,
            method: str,
            endpoint: str,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """统一的HTTP请求封装
        :param method: HTTP方法（GET/POST）
        :param endpoint: API端点
        :param params: 请求参数
        :param headers: 请求头（含签名）
        :return: 响应数据
        """
        try:
            response = requests.request(
                method=method,
                url=self.base_url + endpoint,
                params=params,
                headers=headers or {},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Exchange request failed: {str(e)}")
            raise
