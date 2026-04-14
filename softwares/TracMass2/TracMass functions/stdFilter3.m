function stdMap = stdFilter3( time, data, nFilter )
% locally weighted standard deviation

%by: Magnus Åberg

%stdMap = zeros( size(data));

N = length(data);
if ~isOdd( floor( nFilter ) ), nFilter = floor(nFilter) + 1; end


time = time(:);
data = data(:);

timeFilter = linspace( -3.5, 3.5, nFilter )';

weights = exp( -.5 * timeFilter.^2 );
weights = weights / sum( weights );

xw = maFilt( data, weights );

xxw = maFilt( data.^2, weights );

stdMap = sqrt( ( xxw - xw.^2 ) / ( 1 - sum( weights.^2 ) ) );

% 
% 
% try
%     hi = 1;
%     lo = 1;
%     
%     for i = 1:N,
%         while time(hi)<(time(i)+timeWindow) && hi<N
%             hi = hi+1;
%         end
%         while time(lo)<(time(i)-timeWindow) 
%             lo = lo+1;
%         end
%         weights = exp(-.5*((time(lo:hi)-time(i))/(timeWindow/2)).^2);
%         weights = weights/sum(weights);
%         %tmpData = data(mask); % get the relevant data.
%         tmpData = data(lo:hi); % get the relevant data.
%         tmpData = tmpData - sum(tmpData.*weights); % subtract the weighted mean
%         stdMap(i) = sqrt(sum((tmpData.*weights).^2)./sum(weights.^2)); % compute the weighted sum of squares
%     end
% catch
%     lasterror
%     keyboard
% end