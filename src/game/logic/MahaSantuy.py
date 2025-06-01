from typing import Optional, List, Tuple
from game.logic.base import BaseLogic
from game.models import GameObject, Board, Position

class MahaSantuyLogic(BaseLogic):
    def __init__(self):
        self.move_vectors = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        self.target_spot: Optional[Position] = None
        self.pursuit_count = 0
        self.using_portal = False

    #! DIAMOND SECTION
    def nearby_gems(self, bot: GameObject, board: Board) -> List[Position]:
        """Return a list of diamond positions within 3 tiles of the base."""
        props = bot.properties
        diamonds = board.diamonds
        base_x, base_y = props.base.x, props.base.y
        gem_positions = [diamond.position for diamond in diamonds
                         if base_x - 3 <= diamond.position.x <= base_x + 3
                         and base_y - 3 <= diamond.position.y <= base_y + 3]
        return gem_positions
    
    def is_near_home(self, bot: GameObject) -> bool:
        """Check if the bot is within 3 tiles of its base."""
        props = bot.properties
        current_position = bot.position
        return ((props.base.x - 3) <= current_position.x <= (props.base.x + 3) and 
                (props.base.y - 3) <= current_position.y <= (props.base.y + 3))
    
    def nearest_gem_to_base(self, bot: GameObject, gems: List[Position]) -> Position:
        """Find the diamond closest to the bot among those near the base."""
        current_position = bot.position
        nearest_gem = min(gems, key=lambda gem: abs(gem.x - current_position.x) + abs(gem.y - current_position.y))
        return nearest_gem
    
    def has_gems_near_base(self, bot: GameObject, board: Board) -> bool:
        """Check if there are diamonds within 2 tiles of the base."""
        diamonds = board.diamonds
        for diamond in diamonds:
            if (bot.properties.base.x - 2) <= diamond.position.x <= (bot.properties.base.x + 2) and \
               (bot.properties.base.y - 2) <= diamond.position.y <= (bot.properties.base.y + 2):
                return True
        return False
    
    def nearest_blue_gem(self, bot: GameObject, board: Board) -> Optional[Position]:
        """Find the nearest blue diamond (1 point) to the bot."""
        current_position = bot.position
        diamonds = [diamond for diamond in board.diamonds if diamond.properties.points == 1]
        if not diamonds:
            return None
        nearest_gem = min(diamonds, key=lambda diamond: abs(diamond.position.x - current_position.x) + 
                          abs(diamond.position.y - current_position.y))
        return nearest_gem.position

    def blue_gem_distance(self, bot: GameObject, board: Board) -> int:
        """Calculate the distance to the nearest blue diamond."""
        closest = self.nearest_blue_gem(bot, board)
        current_position = bot.position
        if closest is None:
            return 999
        return abs(closest.x - current_position.x) + abs(closest.y - current_position.y)
    
    def nearest_red_gem(self, bot: GameObject, board: Board) -> Optional[Position]:
        """Find the nearest red diamond (2 points) to the bot."""
        current_position = bot.position
        red_diamonds = [diamond for diamond in board.diamonds if diamond.properties.points == 2]
        if not red_diamonds:
            return None
        nearest_red = min(red_diamonds, key=lambda diamond: abs(diamond.position.x - current_position.x) + 
                          abs(diamond.position.y - current_position.y))
        return nearest_red.position
    
    def red_gem_distance(self, bot: GameObject, board: Board) -> int:
        """Calculate the distance to the nearest red diamond."""
        closest = self.nearest_red_gem(bot, board)
        current_position = bot.position
        if closest is None:
            return 999
        return abs(closest.x - current_position.x) + abs(closest.y - current_position.y)
    
    def home_distance(self, bot: GameObject) -> int:
        """Calculate the distance from the bot to its base."""
        current_position = bot.position
        base = bot.properties.base
        return abs(base.x - current_position.x) + abs(base.y - current_position.y)

    #! DENSITY-BASED STRATEGY
    def get_density(self, diamond: GameObject, bot_pos: Position) -> float:
        """Calculate the density of a diamond (points/distance)."""
        dist = self.needed_steps(bot_pos, diamond.position)
        return diamond.properties.points / dist if dist != 0 else float('inf')

    def needed_steps(self, start: Position, dest: Position) -> int:
        """Calculate the Manhattan distance between two positions."""
        return abs(start.x - dest.x) + abs(start.y - dest.y)

    def best_density_target(self, bot: GameObject, board: Board) -> Optional[Position]:
        """Find the best target based on density, considering direct paths and teleporters."""
        diamonds = board.diamonds
        if not diamonds:
            return None
        bot_position = bot.position
        curr_density_max = 0
        curr_density_max_pos = bot.properties.base  # Default to base if no better target

        # Direct path to diamonds
        for diamond in diamonds:
            density = self.get_density(diamond, bot_position)
            if density > curr_density_max:
                curr_density_max = density
                curr_density_max_pos = diamond.position

        # Check teleporters
        portals = self.find_all_portals(bot, board)
        if len(portals) >= 2:
            marco, polo = portals[0], portals[1]
            dist_to_marco = self.needed_steps(bot_position, marco.position)
            dist_to_polo = self.needed_steps(bot_position, polo.position)
            target_tele, exit_tele = (polo, marco) if dist_to_polo < dist_to_marco else (marco, polo)
            distance_to_tele = self.needed_steps(bot_position, target_tele.position)

            for diamond in diamonds:
                tele_density = diamond.properties.points / (
                    distance_to_tele + self.needed_steps(diamond.position, exit_tele.position)
                ) if (distance_to_tele + self.needed_steps(diamond.position, exit_tele.position)) != 0 else float('inf')
                if tele_density > curr_density_max:
                    curr_density_max = tele_density
                    curr_density_max_pos = target_tele.position

        return curr_density_max_pos

    #! BOT SECTION
    def enemy_distance(self, bot: GameObject, enemy: GameObject) -> Tuple[int, int]:
        """Calculate the (x, y) distance from the bot to an enemy."""
        return (enemy.position.x - bot.position.x, enemy.position.y - bot.position.y)
    
    def find_target_enemies(self, bot: GameObject, board: Board) -> List[GameObject]:
        """Find enemy bots with >=3 diamonds and more diamonds than the bot."""
        enemies = []
        for enemy in board.bots:
            if (enemy.id != bot.id and 
                enemy.properties.base.x != enemy.position.x and 
                enemy.properties.base.y != enemy.position.y):
                if (enemy.properties.diamonds > bot.properties.diamonds and 
                    enemy.properties.diamonds >= 3):
                    enemies.append(enemy)
        return enemies
    
    def pursue_enemies(self, bot: GameObject, board: Board) -> bool:
        """Pursue an enemy if within 3 tiles and bot is within 4 tiles of base."""
        if self.home_distance(bot) <= 4 and self.pursuit_count <= 5:
            enemies = self.find_target_enemies(bot, board)
            for enemy in enemies:
                dist = self.enemy_distance(bot, enemy)
                if dist[0] == 0 and dist[1] == 0:
                    self.target_spot = bot.properties.base
                    return False
                elif abs(dist[0]) <= 3 and abs(dist[1]) <= 3:
                    self.target_spot = enemy.position
                    return True
                else:
                    self.target_spot = None
                    return False
        else:
            self.target_spot = None
            self.pursuit_count = 0
            self.using_portal = False
            return False
    
    #! RED BUTTON
    def locate_red_switch(self, board: Board) -> Optional[GameObject]:
        """Locate the red switch (DiamondButtonGameObject)."""
        for item in board.game_objects:
            if item.type == "DiamondButtonGameObject":
                return item
        return None
    
    def prefer_red_switch(self, bot: GameObject, board: Board) -> bool:
        """Check if the red switch is closer than the nearest blue diamond."""
        if self.nearest_blue_gem(bot, board) is not None:
            red_switch = self.locate_red_switch(board)
            if red_switch and self.red_switch_distance(bot, board) < self.blue_gem_distance(bot, board):
                return True
        return False
    
    def red_switch_distance(self, bot: GameObject, board: Board) -> int:
        """Calculate the distance to the red switch."""
        red_switch = self.locate_red_switch(board)
        if red_switch is None:
            return 999
        return abs(red_switch.position.x - bot.position.x) + abs(red_switch.position.y - bot.position.y)
    
    #! TELEPORTER
    def find_all_portals(self, bot: GameObject, board: Board) -> List[GameObject]:
        """Find all teleporters, sorted by distance from the bot."""
        portals = [item for item in board.game_objects if item.type == "TeleportGameObject"]
        return sorted(portals, key=lambda portal: (abs(portal.position.x - bot.position.x) + 
                                                  abs(portal.position.y - bot.position.y)))
    
    def use_portal_to_base(self, bot: GameObject, board: Board) -> None:
        """Check if using a teleporter to reach the base is faster."""
        portals = self.find_all_portals(bot, board)
        if len(portals) < 2:
            return
        dist_to_base_second = abs(bot.properties.base.y - portals[1].position.y) + \
                              abs(bot.properties.base.x - portals[1].position.x)
        dist_to_base_first = abs(bot.properties.base.y - portals[0].position.y) + \
                             abs(bot.properties.base.x - portals[0].position.x)
        if dist_to_base_second == dist_to_base_first:
            return
        dist_to_bot = abs(bot.position.x - portals[0].position.x) + \
                      abs(bot.position.y - portals[0].position.y)
        if dist_to_base_first + dist_to_bot < self.home_distance(bot):
            self.using_portal = True
            self.target_spot = portals[0].position

    #! GET DIRECTIONS
    def compute_path(self, current_x: int, current_y: int, dest_x: int, dest_y: int) -> Tuple[int, int]:
        """Compute the next move direction towards the destination with zigzag movement."""
        delta_x = abs(dest_x - current_x)
        delta_y = abs(dest_y - current_y)
        x = 0
        y = 0

        if dest_x - current_x < 0:
            x = -1
        else:
            x = 1

        if dest_y - current_y < 0:
            y = -1
        else:
            y = 1

        if delta_x >= delta_y:
            dx = x
            dy = 0
        else:
            dy = y
            dx = 0
        return (dx, dy)

    def next_move(self, bot: GameObject, board: Board) -> Tuple[int, int]:
        """Determine the next move based on multiple greedy strategies."""
        props = bot.properties
        current_position = bot.position
        candidates = []

        # Base return conditions
        if self.home_distance(bot) >= props.milliseconds_left:
            candidates.append((bot.properties.base, 999, "base_time"))  # High priority
        elif (self.home_distance(bot) == 2 and props.diamonds > 2) or \
             (self.home_distance(bot) == 1 and props.diamonds > 0) or \
             props.diamonds == 5:
            candidates.append((bot.properties.base, 999, "base_inventory"))  # High priority

        # Greedy by closest to base
        elif props.diamonds >= 3:
            if self.has_gems_near_base(bot, board):
                gem_list = self.nearby_gems(bot, board)
                target = self.nearest_gem_to_base(bot, gem_list)
                distance = self.needed_steps(current_position, target)
                candidates.append((target, 1/distance if distance != 0 else float('inf'), "near_base"))
            elif self.nearest_blue_gem(bot, board) is not None or self.nearest_red_gem(bot, board) is not None:
                if props.diamonds == 3 and self.red_gem_distance(bot, board) <= 3:
                    target = self.nearest_red_gem(bot, board)
                    distance = self.red_gem_distance(bot, board)
                    candidates.append((target, 2/distance if distance != 0 else float('inf'), "red_gem"))
                elif self.blue_gem_distance(bot, board) <= 3:
                    target = self.nearest_blue_gem(bot, board)
                    distance = self.blue_gem_distance(bot, board)
                    candidates.append((target, 1/distance if distance != 0 else float('inf'), "blue_gem"))
                else:
                    candidates.append((bot.properties.base, 999, "base_fallback"))
            else:
                candidates.append((bot.properties.base, 999, "base_fallback"))

        # Other greedy strategies
        else:
            # Greedy by closest to base (if near base or many gems)
            if (self.has_gems_near_base(bot, board) and self.is_near_home(bot)) or \
               (self.has_gems_near_base(bot, board) and len(self.nearby_gems(bot, board)) >= 3):
                gem_list = self.nearby_gems(bot, board)
                target = self.nearest_gem_to_base(bot, gem_list)
                distance = self.needed_steps(current_position, target)
                candidates.append((target, 1/distance if distance != 0 else float('inf'), "near_base"))

            # Greedy by chasing enemy
            if self.pursue_enemies(bot, board):
                self.pursuit_count += 1
                candidates.append((self.target_spot, 2, "enemy"))  # Higher score for enemies

            # Greedy by inventory (red switch)
            if self.prefer_red_switch(bot, board):
                red_switch = self.locate_red_switch(board)
                if red_switch:
                    distance = self.red_switch_distance(bot, board)
                    candidates.append((red_switch.position, 1.5/distance if distance != 0 else float('inf'), "red_switch"))

            # Greedy by chasing diamond (red or blue)
            if self.nearest_red_gem(bot, board) is not None:
                red_distance = self.red_gem_distance(bot, board)
                candidates.append((self.nearest_red_gem(bot, board), 2/red_distance if red_distance != 0 else float('inf'), "red_gem"))
            if self.nearest_blue_gem(bot, board) is not None:
                blue_distance = self.blue_gem_distance(bot, board)
                candidates.append((self.nearest_blue_gem(bot, board), 1/blue_distance if blue_distance != 0 else float('inf'), "blue_gem"))

            # Greedy by density
            density_target = self.best_density_target(bot, board)
            if density_target:
                # Calculate effective density for scoring
                for diamond in board.diamonds:
                    if diamond.position == density_target:
                        density = self.get_density(diamond, current_position)
                        candidates.append((density_target, density, "density"))
                        break
                else:
                    # If target is a teleporter, calculate density via teleporter
                    portals = self.find_all_portals(bot, board)
                    if len(portals) >= 2:
                        marco, polo = portals[0], portals[1]
                        dist_to_marco = self.needed_steps(current_position, marco.position)
                        dist_to_polo = self.needed_steps(current_position, polo.position)
                        target_tele, exit_tele = (polo, marco) if dist_to_polo < dist_to_marco else (marco, polo)
                        if density_target == target_tele.position:
                            for diamond in board.diamonds:
                                tele_density = diamond.properties.points / (
                                    dist_to_marco + self.needed_steps(diamond.position, exit_tele.position)
                                ) if (dist_to_marco + self.needed_steps(diamond.position, exit_tele.position)) != 0 else float('inf')
                                if tele_density > 0:
                                    candidates.append((density_target, tele_density, "density_tele"))

        # Fallback to base if no candidates
        if not candidates:
            candidates.append((bot.properties.base, 999, "base_fallback"))

        # Choose the best candidate
        # Prioritize base returns, then highest score (density or inverse distance)
        best_candidate = max(candidates, key=lambda x: (x[2] in ["base_time", "base_inventory", "base_fallback"], x[1]))
        self.target_spot = best_candidate[0]

        # Check teleporter for base return if target is base
        if self.target_spot == bot.properties.base and not self.using_portal:
            self.use_portal_to_base(bot, board)

        # Compute movement
        delta_x, delta_y = self.compute_path(
            current_position.x,
            current_position.y,
            self.target_spot.x,
            self.target_spot.y,
        )

        return delta_x, delta_y
