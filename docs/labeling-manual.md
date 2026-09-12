# Labeling manual for ontology version 1

Use this manual for target-conditioned financial aspect classification. Each input has one financial passage, one supplied financial target, and one supplied aspect.

## Labeling order

Use these steps in order:

1. Check the target family.
2. Check if the aspect applies to that family.
3. Find evidence about the supplied target and aspect.
4. Resolve the source, speaker, negation, and time.
5. Select one label from the correct family label set.

## Target and aspect checks

The two valid target families are company and macro indicator. Reject the input as `invalid` when the target is outside these families. Also reject an aspect that does not apply to the target family.

| Aspect | Company | Macro indicator |
|---|:---:|:---:|
| Financial performance | Applicable | Invalid |
| Demand and commercial traction | Applicable | Invalid |
| Operations, supply, and capacity | Applicable | Invalid |
| Financial position and funding | Applicable | Invalid |
| Capital allocation | Applicable | Invalid |
| Management and governance | Applicable | Invalid |
| Legal and regulatory position | Applicable | Invalid |
| Risk and resilience | Applicable | Applicable |
| Outlook and expectations | Applicable | Applicable |
| Current condition | Invalid | Applicable |
| Trend and momentum | Invalid | Applicable |
| Drivers and pressures | Invalid | Applicable |

`Invalid` is a schema result. It is not a sentiment or direction label. Use `insufficient evidence` only when the target–aspect pair is valid.

## Evidence boundary

- Use only the supplied passage.
- Use evidence about the supplied target.
- Use the most specific aspect that the evidence supports.
- Do not copy one claim to more than one aspect only because its effects can reach the other aspects.
- For a company target, a specific subject aspect takes priority over the general outlook aspect. Future time alone does not make a claim an outlook claim.
- Use outlook and expectations when the expectation itself or the broad company outlook is the focus.
- Use risk and resilience when exposure, uncertainty, weakness, or the ability to absorb a shock is the focus.

## Company labels

- `positive`: The evidence is favorable for the company and the supplied aspect.
- `negative`: The evidence is unfavorable for the company and the supplied aspect.
- `neutral`: The passage states stability, no material effect, or an explicit net result that is neither favorable nor unfavorable.
- `insufficient evidence`: The evidence is absent, unclear, conflicting without a resolution, or about another aspect.

An explicit statement of no material effect supports `neutral` for the specific company aspect. This rule also applies when the statement refers to a future period.

## Macro-indicator labels

- `increase`: The stated measure, or pressure on it, moves up.
- `decrease`: The stated measure, or pressure on it, moves down.
- `unchanged`: The passage states stability or no material movement in the stated measure.
- `insufficient evidence`: The direction is absent, unclear, or conflicting without a resolution.

Use the movement of the stated measure. Do not use whether the movement is good or bad. Do not change the label because the result differs from a forecast.

Distinguish a level from its rate of change. For example, a wage-growth rate of 4% in two periods is `unchanged`. Wage levels can continue to rise, but the stated growth rate did not change.

## Mixed evidence

Use this order:

1. Use an explicit overall result when the passage gives one.
2. Use the relevant aggregate when subparts move in different directions.
3. Use `neutral` or `unchanged` only when the passage supports no net movement or no material effect.
4. Use `insufficient evidence` when material claims conflict and the passage gives no resolution or basis to combine them.

Do not choose one claim because you personally trust its speaker. A claim from an analyst does not automatically have more weight than a claim from management. The reverse is also true.

## Negation and time

- Resolve the exact scope of a negative word.
- “Did not fall” does not by itself mean “rose.”
- Match the evidence to the time in the passage.
- Do not use a past result for an outlook claim.
- Future time can support a specific company aspect when that subject is the focus.

## Reported speech and source claims

- Treat a clearly attributed claim as passage evidence.
- Keep the speaker clear.
- If the passage rejects a reported claim, do not treat the rejected claim as fact.
- Do not change the label because of a personal view of source reliability.
- The experiment can record source and speaker information as metadata. It must not change the reference label.

## Sarcasm

Use the intended meaning only when the words and context make it clear. Use `insufficient evidence` when the intended meaning is unclear.

## Cross-target effects

Do not transfer a result from one target to another target. Use a cross-target effect only when the passage states the effect on the supplied target.

## Prototype result

One human applied the draft manual to 10 difficult synthetic cases. The cases covered all five passage sources and both target families. Seven labels matched the draft. Three disagreements exposed these rule boundaries:

- A future no-material-effect statement about operations is `neutral` for operations. It is not moved to outlook only because it refers to the future.
- Personal trust in an analyst does not resolve a conflict between analyst and management claims. The unresolved label is `insufficient evidence`.
- A stable positive wage-growth rate is `unchanged` when the stated measure is the growth rate.

These changes are part of ontology version 1.

The primary evidence is on the throwaway prototype branch:

- [Interactive labeling prototype](https://github.com/neoyipeng2018/nlp-wayfinder/blob/60ebe7839db031409b204986174c4252f5458819/.scratch/sub-100-financial-aspect-sentiment/labeling-manual-prototype.html)
- [Human review data](https://github.com/neoyipeng2018/nlp-wayfinder/blob/60ebe7839db031409b204986174c4252f5458819/.scratch/sub-100-financial-aspect-sentiment/labeling-manual-review.json)
