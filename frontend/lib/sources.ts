// AI-generated with Claude (Anthropic).
// Methodology notes and citations shown on the landing page.
// Every citation below was checked against its DOI or publisher page. Only add verified sources.

export interface Cite { label: string; url: string }
export interface Method { title: string; body: string; cites: Cite[] }

export const SOURCES: { methods: Method[]; caveat: string } = {
  methods: [
    {
      title: "Pricing from a forecast distribution",
      body: "Each temperature range is priced at the probability the forecast gives it. This is the index-modelling approach to valuing weather contracts, with weather-model forecasts supplying the distribution for the next day.",
      cites: [
        { label: "Jewson & Brix, Weather Derivative Valuation (Cambridge University Press, 2005)", url: "https://doi.org/10.1017/CBO9780511493348" },
        { label: "Campbell & Diebold, Journal of the American Statistical Association (2005)", url: "https://doi.org/10.1198/016214504000001051" },
      ],
    },
    {
      title: "Premium = expected payout + a loading",
      body: "What the pool pays is the expected payout of its contracts plus the market maker's spread. That is the expected-value premium principle insurers use: expected loss plus a risk loading.",
      cites: [
        { label: "Dickson, Insurance Risk and Ruin, ch. 3 (Cambridge University Press, 2005)", url: "https://doi.org/10.1017/CBO9780511624155" },
        { label: "Bühlmann, Mathematical Methods in Risk Theory (Springer, 1970)", url: "https://doi.org/10.1007/978-3-540-30711-2" },
      ],
    },
    {
      title: "Pooling offsetting risks",
      body: "Businesses hurt by heat and by cold are combined before hedging, so opposite exposures cancel and only the net is bought on Gemini. Sharing risks across a pool beats each party carrying its own, and diversification lowers the capital a portfolio of risks needs.",
      cites: [
        { label: "Borch, Econometrica (1962)", url: "https://doi.org/10.2307/1909887" },
        { label: "Cummins, Risk Management and Insurance Review (2000)", url: "https://doi.org/10.1111/j.1540-6296.2000.tb00013.x" },
      ],
    },
    {
      title: "Why hedging weather is worth it",
      body: "When weather derivatives became available, weather-exposed firms that used them gained market value, invested more and could borrow more.",
      cites: [
        { label: "Pérez-González & Yun, Journal of Finance (2013)", url: "https://doi.org/10.1111/jofi.12061" },
      ],
    },
    {
      title: "How much sales move with temperature",
      body: "Published estimates exist for some categories: French apparel sales move about 1.9–2.2% per °C of unusual temperature in spring and fall, and one-day weather shocks shift US apparel and sporting-goods sales by about 10% over four weeks. Some of the lost sales are only delayed, and return within the quarter.",
      cites: [
        { label: "Bertrand, Brusset & Fortin, European Journal of Operational Research (2015)", url: "https://doi.org/10.1016/j.ejor.2015.01.012" },
        { label: "Roth Tran, Management Science (2023)", url: "https://doi.org/10.1287/mnsc.2023.4799" },
        { label: "Starr-McCluer, Federal Reserve FEDS working paper (2000)", url: "https://www.federalreserve.gov/econres/feds/the-effects-of-weather-on-retail-sales.htm" },
      ],
    },
  ],
  caveat:
    "Each business's dollars-per-degree figure is our estimate from its business type and revenue (1–2.5% of daily revenue per °F), not from its own sales history. We found no peer-reviewed per-degree estimates for ice cream, coffee or restaurants specifically. With a year of a business's daily sales, the figure can be fitted directly by regressing sales on temperature.",
};
