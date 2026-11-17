"""Notează evaluarea de declanșare: trigger_answers.json vs. expect din trigger_set.json."""
import json
s = json.load(open("trigger_set.json"))["queries"]
a = json.load(open("trigger_answers.json"))
tp = sum(q["expect"] == "aviator-mergequeue" and x == "aviator-mergequeue" for q, x in zip(s, a))
fp = sum(q["expect"] != "aviator-mergequeue" and x == "aviator-mergequeue" for q, x in zip(s, a))
pos = sum(q["expect"] == "aviator-mergequeue" for q in s)
acc = sum(q["expect"] == x for q, x in zip(s, a)) / len(s)
r = {"recall": tp / pos, "false_triggers": fp, "routing_accuracy": acc, "n": len(s)}
json.dump(r, open("trigger_rezultate.json", "w"), indent=1); print(r)
