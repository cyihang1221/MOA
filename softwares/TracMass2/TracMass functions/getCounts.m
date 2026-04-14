function [c,ref]=getCounts(x,ref)
% [c]=getCounts(x,ref)
% x - vector of values which are to be counted
% ref - vector of reference values to get counts for

%by: Magnus Åberg
str = ''; idisp = 1;
if nargin == 1,
   ref = unique(x); 
   c = diff([-inf;x(:)]); 
   inds = find(c)-1; % bug fix 2008-07-01 MÅ
   c = diff([inds;numel(c)]);% % bug fix 2008-07-01 MÅ
   return
end
if isempty(ref)
   c =[];
   return
end
if isempty(x)
   c = zeros(size(ref(:)));
   return
end
ref = sort(ref(:));

x = sort(x(:));
x(x<ref(1)) = [];
x(x>ref(end)) = [];

nRef = numel(ref);
nPoints = numel(x);

k = 1;
iRef = 1;
c = zeros(size(ref));
done = false;
while iRef<=nRef && ~done
   iStart = k;
   while x(k)==ref(iRef),
      k=k+1;
      if k>=nPoints
         k=nPoints;
         done = true;
         break
      end
   end
   iStop = k;
   if done && x(k)==ref(iRef),
      iStop = iStop+1;
   else
      done = false;
   end
   c(iRef) = iStop-iStart;
   iRef = iRef+1;
end