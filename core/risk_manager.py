# core/risk_manager.py
class RiskManager:
    def calculate_required_margin(self, position):
        # 实时计算多仓合并后的保证金需求
        pass

def check_liquidation(self):
    while True:
        current_price = get_live_price("BTCUSDT")
        for position in open_positions:
            if is_liquidation_position(position, current_price):
                trigger_alert("Position liquidated!")
                execute_force_close(position)