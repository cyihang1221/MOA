function clust = find_cluster3(L,N)
%Magnus Åberg

L = sortrows(L);
C = getCounts(L(:,1),(1:max(L(:,1))));
S = cumsum([0; C(1:end-1)]);

is = 0;nS = numel(S);
chk = false(size(S));

clust = zeros(N,1);
fifo('init',[1000,1])
iClust = 0;
cnt = 0;
%% fifo
dim = [1e4 1];
q = nan(dim);
first = 1;
count = 0;
last  = 0;
   function fifo_add(x)
      x = x(:);
      k = numel(x);
      
      if count+k> dim(1),
         [q,first,last,dim] = alloc(q,first,last,dim);
      elseif last+k>dim(1)
         [q,first,last] = shift(q,first,last);
      end
      ii = last + (1:k);
      q(ii,:) = x;
      count = count + k;
      last = last + k;
   end
   function x=fifo_pop
      if count==0,
         x=[];
      else
         x=q(first,:);
         first = first+1;
         count = count-1;
      end
      if count==0
         first = 1;
         last = 0;
      end
   end
   function tf = fifo_isempty
      tf = count==0;
   end

%% do the work
   function do_chk(j)
      chk(j) = true;
      if C(j)==0, return,end
      l = unique(L(S(j) + (1:C(j)),:));
      theClust = max(clust(l));
      
      if theClust == 0;
         iClust = iClust +1;
         theClust = iClust;
      end
      %if numel(unique(clust(l(clust(l)>0))))>1,disp('inconsistency'),keyboard,end
      mask = clust(l)>0;
      clust(l(~mask)) = theClust;
      mask = chk(l)|mask;
      fifo_add(l(~mask));
      cnt = cnt+1;
   end

for is=1:nS,
   if ~chk(is),do_chk(is);end
   while ~fifo_isempty
      j = fifo_pop;
      if ~chk(j)
         do_chk(j)
      end
   end
end
% disp('find_cluster3: [cnt, n]')
% disp([cnt N])
end

%% fifo helpers
function [q,first,last,dim]=alloc(q,first,last,dim)
tmp = q(first:last,:);
n = size(q,1);
dim(1) = n+dim(1);
q = nan(dim);
q(1:(last-first+1),:)=tmp;
last = last-first+1;
first = 1;
end

function [q,first,last] = shift(q,first,last)
n = last-first+1;
q(1:n,:) = q(first:last,:);
first = 1;
last = n;
q(n+1,:) = nan;
end