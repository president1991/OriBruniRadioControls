class MeshNode:
    def __init__(self, id, user, battery_level):
        self.id = id
        self.user = user
        self.battery_level = battery_level

    def __repr__(self):
        return f"<MeshNode {self.user} ({self.id}) - Battery: {self.battery_level}%>"