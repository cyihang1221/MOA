function m=moving_average(x,n)
%by: Magnus Åberg

assert(isOdd(n));
% k = floor(n/2);
% ii = -k:k;
% N = numel(x);
% m = zeros(size(x));
% for i = 1:N
%    inds = i+ii;
%    inds(inds<1 | inds>N)=[];
%    m(i) = mean(x(inds));
% end

f = ones(n,1)/n;
transpose = size(x,1)==1;
m = maFilt(x(:),f);
if transpose
   m = m';
end