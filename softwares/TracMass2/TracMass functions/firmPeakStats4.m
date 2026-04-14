function peakSummary = firmPeakStats4(peakList)
%Magnus Åberg

peakList = sortTable(peakList,'gid');
[c,ii,ids]= getCounts2(peakList.gid);
mask=ids==0;
c(mask)=[];
ii(mask)=[];
ids(mask)=[];

dim = size(ids);

peakSummary.id = ids;

peakSummary.count = c;

peakSummary.timeMean   = zeros(dim);
peakSummary.timeMedian = zeros(dim);
peakSummary.timeMin    = zeros(dim);
peakSummary.timeMax    = zeros(dim);
peakSummary.timeStd    = zeros(dim);

peakSummary.massMean   = zeros(dim);
peakSummary.massMedian = zeros(dim);
peakSummary.massMin    = zeros(dim);
peakSummary.massMax    = zeros(dim);
peakSummary.massStd    = zeros(dim);

peakSummary.intensityMean   = zeros(dim);
peakSummary.intensityMedian = zeros(dim);
peakSummary.intensityMin    = zeros(dim);
peakSummary.intensityMax    = zeros(dim);
peakSummary.intensityStd    = zeros(dim);

compHScore = isfield( peakList, 'hScore' );
if compHScore,
    peakSummary.houghScore      = zeros(dim);
end

for i = 1:numel(ids)
   inds = ii(i) + (1:c(i));
   assert(all(peakList.gid(inds)==ids(i)));
   time = peakList.time(inds);
   mass = peakList.mass(inds);
   intensity = peakList.intensity(inds);
   
   peakSummary.timeMean(i)   = mean(time);
   peakSummary.timeMedian(i) = median(time);
   peakSummary.timeMin(i)    = min(time);
   peakSummary.timeMax(i)    = max(time);
   peakSummary.timeStd(i)    = std(time);

   peakSummary.massMean(i)   = mean(mass);
   peakSummary.massMedian(i) = median(mass);
   peakSummary.massMin(i)    = min(mass);
   peakSummary.massMax(i)    = max(mass);
   peakSummary.massStd(i)    = std(mass);
   
   peakSummary.intensityMean(i)   = mean(intensity);
   peakSummary.intensityMedian(i) = median(intensity);
   peakSummary.intensityMin(i)    = min(intensity);
   peakSummary.intensityMax(i)    = max(intensity);
   peakSummary.intensityStd(i)    = std(intensity);
   
%    if compHScore
%        peakSummary.houghScore( i )    = mean( peakList.hScore( inds ) );
%    end
end

